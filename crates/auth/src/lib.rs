//! SQLite-backed users + JWT sessions for gateway auth.

use anyhow::{anyhow, Context, Result};
use argon2::{
    password_hash::{PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use rand::rngs::OsRng;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Mutex;
use thiserror::Error;
use time::OffsetDateTime;
use uuid::Uuid;

const MIGRATION_SQL: &str = include_str!("../migrations/001_users.sql");

/// Floor for the bootstrap admin password. Short enough not to obstruct setup,
/// long enough that the first account isn't brute-forceable.
const MIN_BOOTSTRAP_PASSWORD_LEN: usize = 12;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    Admin,
    Member,
}

impl Role {
    pub fn as_str(self) -> &'static str {
        match self {
            Role::Admin => "admin",
            Role::Member => "member",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().as_str() {
            "admin" => Some(Role::Admin),
            "member" => Some(Role::Member),
            _ => None,
        }
    }

    pub fn is_admin(self) -> bool {
        matches!(self, Role::Admin)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub username: String,
    pub role: Role,
    pub created_at: String,
    pub disabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub username: String,
    pub role: Role,
    pub exp: usize,
}

#[derive(Clone)]
pub struct AuthConfig {
    pub db_path: String,
    pub jwt_secret: String,
    pub jwt_ttl_secs: u64,
    pub cookie_name: String,
    pub cookie_secure: bool,
    pub allow_public_register: bool,
    pub disabled: bool,
    pub bootstrap_user: Option<String>,
    pub bootstrap_password: Option<String>,
}

impl std::fmt::Debug for AuthConfig {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // `jwt_secret` and `bootstrap_password` must never reach a log line.
        f.debug_struct("AuthConfig")
            .field("db_path", &self.db_path)
            .field("jwt_secret", &"<redacted>")
            .field("jwt_ttl_secs", &self.jwt_ttl_secs)
            .field("cookie_name", &self.cookie_name)
            .field("cookie_secure", &self.cookie_secure)
            .field("allow_public_register", &self.allow_public_register)
            .field("disabled", &self.disabled)
            .field("bootstrap_user", &self.bootstrap_user)
            .field("bootstrap_password", &"<redacted>")
            .finish()
    }
}

impl AuthConfig {
    pub fn from_env() -> Result<Self> {
        let disabled = std::env::var("AUTH_DISABLE")
            .ok()
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
            .unwrap_or(false);
        // No fallback secret: a hardcoded default is guessable, and the previous
        // one was 36 bytes so it slipped past the length check below.
        let jwt_secret = match std::env::var("AUTH_JWT_SECRET") {
            Ok(s) => s,
            Err(_) if disabled => String::new(),
            Err(_) => anyhow::bail!(
                "AUTH_JWT_SECRET is required (>=32 bytes). Set AUTH_DISABLE=1 for local dev only."
            ),
        };
        if !disabled && jwt_secret.len() < 32 {
            anyhow::bail!("AUTH_JWT_SECRET must be at least 32 bytes when auth enabled");
        }
        if disabled {
            tracing::warn!(
                "AUTH_DISABLE=1 — every request is treated as admin. Never use in production."
            );
        }
        Ok(Self {
            db_path: std::env::var("AUTH_DB_PATH").unwrap_or_else(|_| "data/auth.db".into()),
            jwt_secret,
            jwt_ttl_secs: std::env::var("AUTH_JWT_TTL_SECS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(86_400),
            cookie_name: std::env::var("AUTH_COOKIE_NAME").unwrap_or_else(|_| "gws_session".into()),
            cookie_secure: std::env::var("AUTH_COOKIE_SECURE")
                .ok()
                .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                .unwrap_or(false),
            allow_public_register: std::env::var("AUTH_ALLOW_PUBLIC_REGISTER")
                .ok()
                .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                .unwrap_or(false),
            disabled,
            bootstrap_user: std::env::var("AUTH_BOOTSTRAP_ADMIN_USER").ok(),
            bootstrap_password: std::env::var("AUTH_BOOTSTRAP_ADMIN_PASSWORD").ok(),
        })
    }
}

pub struct AuthService {
    conn: Mutex<Connection>,
    cfg: AuthConfig,
}

impl std::fmt::Debug for AuthService {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // Hand-written: AuthConfig carries the JWT secret, so a derive would
        // print it on any `{:?}` of the service.
        f.debug_struct("AuthService")
            .field("db_path", &self.cfg.db_path)
            .field("disabled", &self.cfg.disabled)
            .finish_non_exhaustive()
    }
}

#[derive(Debug, Error)]
pub enum AuthError {
    #[error("invalid credentials")]
    InvalidCredentials,
    #[error("user exists")]
    UserExists,
    #[error("user not found")]
    NotFound,
    #[error("forbidden")]
    Forbidden,
    #[error("disabled")]
    Disabled,
    #[error("invalid token")]
    InvalidToken,
    #[error("{0}")]
    Other(String),
}

impl AuthService {
    pub fn open(cfg: AuthConfig) -> Result<Self> {
        if let Some(parent) = Path::new(&cfg.db_path).parent() {
            std::fs::create_dir_all(parent)
                .with_context(|| format!("create auth db parent {:?}", parent))?;
        }
        let conn = Connection::open(&cfg.db_path)
            .with_context(|| format!("open auth db {}", cfg.db_path))?;
        conn.execute_batch(MIGRATION_SQL)
            .context("run auth migrations")?;
        let svc = Self {
            conn: Mutex::new(conn),
            cfg,
        };
        svc.bootstrap_admin_if_empty()?;
        Ok(svc)
    }

    pub fn config(&self) -> &AuthConfig {
        &self.cfg
    }

    fn bootstrap_admin_if_empty(&self) -> Result<()> {
        let count: i64 = self
            .conn
            .lock()
            .map_err(|e| anyhow!(e.to_string()))?
            .query_row("SELECT COUNT(*) FROM users", [], |r| r.get(0))?;
        if count > 0 {
            return Ok(());
        }
        // Seeding a well-known admin/password pair would make every default
        // deployment trivially reachable, so an empty DB is a hard stop.
        let (user, pass) = match (
            self.cfg.bootstrap_user.as_deref(),
            self.cfg.bootstrap_password.as_deref(),
        ) {
            (Some(u), Some(p)) if !u.trim().is_empty() && !p.is_empty() => (u, p),
            _ => anyhow::bail!(
                "auth db has no users; set AUTH_BOOTSTRAP_ADMIN_USER and \
                 AUTH_BOOTSTRAP_ADMIN_PASSWORD to create the first admin"
            ),
        };
        if pass.len() < MIN_BOOTSTRAP_PASSWORD_LEN {
            anyhow::bail!(
                "AUTH_BOOTSTRAP_ADMIN_PASSWORD must be at least {MIN_BOOTSTRAP_PASSWORD_LEN} bytes"
            );
        }
        self.create_user(user, pass, Role::Admin)?;
        tracing::info!(user, "bootstrapped initial admin");
        Ok(())
    }

    pub fn hash_password(password: &str) -> Result<String> {
        let salt = SaltString::generate(&mut OsRng);
        let hash = Argon2::default()
            .hash_password(password.as_bytes(), &salt)
            .map_err(|e| anyhow!(e.to_string()))?
            .to_string();
        Ok(hash)
    }

    pub fn verify_password(password: &str, hash: &str) -> bool {
        let parsed = match PasswordHash::new(hash) {
            Ok(h) => h,
            Err(_) => return false,
        };
        Argon2::default()
            .verify_password(password.as_bytes(), &parsed)
            .is_ok()
    }

    pub fn create_user(
        &self,
        username: &str,
        password: &str,
        role: Role,
    ) -> Result<User, AuthError> {
        let username = username.trim();
        if username.is_empty() || password.is_empty() {
            return Err(AuthError::Other("username and password required".into()));
        }
        let id = Uuid::new_v4().to_string();
        let created_at = OffsetDateTime::now_utc()
            .format(&time::format_description::well_known::Rfc3339)
            .unwrap_or_else(|_| "1970-01-01T00:00:00Z".into());
        let password_hash =
            Self::hash_password(password).map_err(|e| AuthError::Other(e.to_string()))?;
        let conn = self
            .conn
            .lock()
            .map_err(|e| AuthError::Other(e.to_string()))?;
        match conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, disabled) VALUES (?1, ?2, ?3, ?4, ?5, 0)",
            params![id, username, password_hash, role.as_str(), created_at],
        ) {
            Ok(_) => Ok(User {
                id,
                username: username.to_string(),
                role,
                created_at,
                disabled: false,
            }),
            Err(rusqlite::Error::SqliteFailure(err, _))
                if err.code == rusqlite::ErrorCode::ConstraintViolation =>
            {
                Err(AuthError::UserExists)
            }
            Err(e) => Err(AuthError::Other(e.to_string())),
        }
    }

    pub fn authenticate(&self, username: &str, password: &str) -> Result<User, AuthError> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AuthError::Other(e.to_string()))?;
        let row = conn
            .query_row(
                "SELECT id, username, password_hash, role, created_at, disabled FROM users WHERE username = ?1 COLLATE NOCASE",
                params![username.trim()],
                |r| {
                    Ok((
                        r.get::<_, String>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, String>(2)?,
                        r.get::<_, String>(3)?,
                        r.get::<_, String>(4)?,
                        r.get::<_, i64>(5)? != 0,
                    ))
                },
            )
            .map_err(|_| AuthError::InvalidCredentials)?;
        let (id, uname, hash, role_s, created_at, disabled) = row;
        if disabled {
            return Err(AuthError::Disabled);
        }
        if !Self::verify_password(password, &hash) {
            return Err(AuthError::InvalidCredentials);
        }
        let role = Role::parse(&role_s).ok_or_else(|| AuthError::Other("bad role in db".into()))?;
        Ok(User {
            id,
            username: uname,
            role,
            created_at,
            disabled,
        })
    }

    pub fn issue_token(&self, user: &User) -> Result<String, AuthError> {
        let exp = (OffsetDateTime::now_utc().unix_timestamp() as u64)
            .saturating_add(self.cfg.jwt_ttl_secs);
        let claims = Claims {
            sub: user.id.clone(),
            username: user.username.clone(),
            role: user.role,
            exp: exp as usize,
        };
        encode(
            &Header::default(),
            &claims,
            &EncodingKey::from_secret(self.cfg.jwt_secret.as_bytes()),
        )
        .map_err(|e| AuthError::Other(e.to_string()))
    }

    pub fn verify_token(&self, token: &str) -> Result<Claims, AuthError> {
        let data = decode::<Claims>(
            token,
            &DecodingKey::from_secret(self.cfg.jwt_secret.as_bytes()),
            &Validation::default(),
        )
        .map_err(|_| AuthError::InvalidToken)?;
        Ok(data.claims)
    }

    pub fn get_user_by_id(&self, id: &str) -> Result<User, AuthError> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AuthError::Other(e.to_string()))?;
        conn.query_row(
            "SELECT id, username, role, created_at, disabled FROM users WHERE id = ?1",
            params![id],
            |r| {
                let role_s: String = r.get(2)?;
                Ok(User {
                    id: r.get(0)?,
                    username: r.get(1)?,
                    role: Role::parse(&role_s).unwrap_or(Role::Member),
                    created_at: r.get(3)?,
                    disabled: r.get::<_, i64>(4)? != 0,
                })
            },
        )
        .map_err(|_| AuthError::NotFound)
    }

    pub fn list_users(&self) -> Result<Vec<User>, AuthError> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AuthError::Other(e.to_string()))?;
        let mut stmt = conn
            .prepare(
                "SELECT id, username, role, created_at, disabled FROM users ORDER BY created_at",
            )
            .map_err(|e| AuthError::Other(e.to_string()))?;
        let rows = stmt
            .query_map([], |r| {
                let role_s: String = r.get(2)?;
                Ok(User {
                    id: r.get(0)?,
                    username: r.get(1)?,
                    role: Role::parse(&role_s).unwrap_or(Role::Member),
                    created_at: r.get(3)?,
                    disabled: r.get::<_, i64>(4)? != 0,
                })
            })
            .map_err(|e| AuthError::Other(e.to_string()))?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|e| AuthError::Other(e.to_string()))
    }

    pub fn set_disabled(&self, user_id: &str, disabled: bool) -> Result<(), AuthError> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AuthError::Other(e.to_string()))?;
        let n = conn
            .execute(
                "UPDATE users SET disabled = ?1 WHERE id = ?2",
                params![if disabled { 1 } else { 0 }, user_id],
            )
            .map_err(|e| AuthError::Other(e.to_string()))?;
        if n == 0 {
            return Err(AuthError::NotFound);
        }
        Ok(())
    }

    /// Change a user's role. Takes effect on the next request because
    /// `require_auth` re-reads the row rather than trusting the token claim.
    pub fn set_role(&self, user_id: &str, role: Role) -> Result<(), AuthError> {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AuthError::Other(e.to_string()))?;
        let n = conn
            .execute(
                "UPDATE users SET role = ?1 WHERE id = ?2",
                params![role.as_str(), user_id],
            )
            .map_err(|e| AuthError::Other(e.to_string()))?;
        if n == 0 {
            return Err(AuthError::NotFound);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_cfg() -> AuthConfig {
        let path = std::env::temp_dir().join(format!("auth-test-{}.db", Uuid::new_v4()));
        AuthConfig {
            db_path: path.to_string_lossy().into(),
            jwt_secret: "test-secret-at-least-32-bytes-long!!".into(),
            jwt_ttl_secs: 3600,
            cookie_name: "gws_session".into(),
            cookie_secure: false,
            allow_public_register: false,
            disabled: false,
            bootstrap_user: Some("admin".into()),
            bootstrap_password: Some("bootstrap-pass-ok".into()),
        }
    }

    #[test]
    fn hash_and_verify_roundtrip() {
        let hash = AuthService::hash_password("hunter2").unwrap();
        assert!(AuthService::verify_password("hunter2", &hash));
        assert!(!AuthService::verify_password("wrong", &hash));
    }

    #[test]
    fn bootstrap_and_login() {
        let svc = AuthService::open(temp_cfg()).unwrap();
        let user = svc.authenticate("admin", "bootstrap-pass-ok").unwrap();
        assert_eq!(user.role, Role::Admin);
        let token = svc.issue_token(&user).unwrap();
        let claims = svc.verify_token(&token).unwrap();
        assert_eq!(claims.username, "admin");
    }

    #[test]
    fn open_fails_without_bootstrap_credentials() {
        let cfg = AuthConfig {
            bootstrap_user: None,
            bootstrap_password: None,
            ..temp_cfg()
        };
        let err = AuthService::open(cfg).expect_err("must not seed a default admin");
        assert!(err.to_string().contains("AUTH_BOOTSTRAP_ADMIN_USER"));
    }

    #[test]
    fn open_rejects_short_bootstrap_password() {
        let cfg = AuthConfig {
            bootstrap_password: Some("short".into()),
            ..temp_cfg()
        };
        let err = AuthService::open(cfg).expect_err("weak bootstrap password must be refused");
        assert!(err.to_string().contains("at least"));
    }

    #[test]
    fn disabled_user_cannot_authenticate() {
        let svc = AuthService::open(temp_cfg()).unwrap();
        let member = svc
            .create_user("member1", "member-pass", Role::Member)
            .unwrap();
        svc.set_disabled(&member.id, true).unwrap();
        let err = svc.authenticate("member1", "member-pass").unwrap_err();
        assert!(matches!(err, AuthError::Disabled));
    }

    #[test]
    fn disabled_flag_is_visible_after_reload() {
        let cfg = temp_cfg();
        let member_id = {
            let svc = AuthService::open(cfg.clone()).unwrap();
            let m = svc
                .create_user("member2", "member-pass", Role::Member)
                .unwrap();
            svc.set_disabled(&m.id, true).unwrap();
            m.id
        };
        // Middleware re-reads the row on every request, so persistence matters.
        let reopened = AuthService::open(cfg).unwrap();
        assert!(reopened.get_user_by_id(&member_id).unwrap().disabled);
    }

    #[test]
    fn duplicate_username_is_rejected() {
        let svc = AuthService::open(temp_cfg()).unwrap();
        svc.create_user("dup", "first-pass", Role::Member).unwrap();
        let err = svc
            .create_user("dup", "second-pass", Role::Member)
            .unwrap_err();
        assert!(matches!(err, AuthError::UserExists));
    }

    #[test]
    fn token_from_other_secret_is_rejected() {
        let svc = AuthService::open(temp_cfg()).unwrap();
        let user = svc.authenticate("admin", "bootstrap-pass-ok").unwrap();
        let token = svc.issue_token(&user).unwrap();

        let other = AuthService::open(AuthConfig {
            jwt_secret: "a-completely-different-secret-32b!!!".into(),
            ..temp_cfg()
        })
        .unwrap();
        assert!(matches!(
            other.verify_token(&token),
            Err(AuthError::InvalidToken)
        ));
    }

    #[test]
    fn role_parse() {
        assert_eq!(Role::parse("admin"), Some(Role::Admin));
        assert_eq!(Role::parse("MEMBER"), Some(Role::Member));
        assert_eq!(Role::parse("x"), None);
    }

    #[test]
    fn debug_redacts_secrets() {
        let rendered = format!("{:?}", temp_cfg());
        assert!(rendered.contains("<redacted>"));
        assert!(!rendered.contains("test-secret-at-least-32-bytes-long"));
        assert!(!rendered.contains("bootstrap-pass-ok"));
    }
}
