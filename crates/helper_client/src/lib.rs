//! Client for the local curl_cffi / protocol bridge helper.

use anyhow::{anyhow, Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::time::Duration;

#[derive(Clone)]
pub struct HelperClient {
    base: String,
    http: Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PinAccount {
    pub email: String,
    #[serde(default)]
    pub access_token: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proxy: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_agent: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct TextRunRequest {
    pub account: PinAccount,
    pub prompt: String,
    #[serde(default)]
    pub model: String,
}

#[derive(Debug, Serialize)]
pub struct ImageRunRequest {
    pub account: PinAccount,
    pub prompt: String,
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub size: String,
}

#[derive(Debug, Serialize)]
pub struct QuotaRefreshRequest {
    pub account: PinAccount,
    #[serde(default = "default_min_remaining")]
    pub min_remaining: i64,
}

#[allow(dead_code)] // referenced by serde default=
fn default_min_remaining() -> i64 {
    1
}

#[derive(Debug, Deserialize)]
pub struct BridgeOk {
    pub ok: bool,
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub b64_json: Option<String>,
    #[serde(default)]
    pub conversation_id: Option<String>,
    #[serde(default)]
    pub fault: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub elapsed_ms: Option<u64>,
    #[serde(default)]
    pub raw: Option<Value>,
    #[serde(default)]
    pub quota: Option<Value>,
}

#[derive(Debug, Deserialize)]
pub struct QuotaOk {
    pub ok: bool,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub plan: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub remaining: Option<i64>,
    #[serde(default)]
    pub restore_at: Option<String>,
    #[serde(default)]
    pub image_quota_unknown: Option<bool>,
    #[serde(default)]
    pub min_remaining: Option<i64>,
    #[serde(default)]
    pub imageable: Option<bool>,
    #[serde(default)]
    pub image_gen: Option<Value>,
    #[serde(default)]
    pub fault: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub elapsed_ms: Option<u64>,
}

impl HelperClient {
    pub fn new(base: impl Into<String>) -> Result<Self> {
        let http = Client::builder()
            .timeout(Duration::from_secs(120))
            .build()
            .context("build helper http client")?;
        Ok(Self {
            base: base.into().trim_end_matches('/').to_string(),
            http,
        })
    }

    pub async fn health(&self) -> Result<Value> {
        let url = format!("{}/health", self.base);
        let resp = self.http.get(url).send().await.context("helper health")?;
        let status = resp.status();
        let body: Value = resp.json().await.unwrap_or_else(|_| serde_json::json!({}));
        if !status.is_success() {
            return Err(anyhow!("helper health status={status} body={body}"));
        }
        Ok(body)
    }

    pub async fn refresh_quota(&self, req: &QuotaRefreshRequest) -> Result<QuotaOk> {
        let url = format!("{}/v1/internal/quota/refresh", self.base);
        let resp = self
            .http
            .post(url)
            .json(req)
            .send()
            .await
            .context("helper POST /v1/internal/quota/refresh")?;
        let status = resp.status();
        let parsed: QuotaOk = resp
            .json()
            .await
            .context("helper decode quota refresh")?;
        if !status.is_success() && parsed.error.is_none() {
            return Err(anyhow!(
                "helper quota status={status} err={:?}",
                parsed.error
            ));
        }
        Ok(parsed)
    }

    pub async fn list_candidates(&self, limit: usize) -> Result<Vec<PinAccount>> {
        let url = format!("{}/v1/internal/accounts/candidates?limit={limit}", self.base);
        let resp = self
            .http
            .get(url)
            .send()
            .await
            .context("helper GET /v1/internal/accounts/candidates")?;
        let status = resp.status();
        #[derive(Deserialize)]
        struct CandBody {
            ok: bool,
            #[serde(default)]
            accounts: Vec<PinAccount>,
            #[serde(default)]
            error: Option<String>,
        }
        let parsed: CandBody = resp
            .json()
            .await
            .context("helper decode candidates")?;
        if !status.is_success() || !parsed.ok {
            return Err(anyhow!(
                "helper candidates status={status} err={:?}",
                parsed.error
            ));
        }
        Ok(parsed.accounts)
    }

    pub async fn run_text(&self, req: &TextRunRequest) -> Result<BridgeOk> {
        self.post_json("/v1/internal/text", req).await
    }

    pub async fn run_image(&self, req: &ImageRunRequest) -> Result<BridgeOk> {
        // Image path may take ~40-80s; use a dedicated longer client.
        let url = format!("{}/v1/internal/image", self.base);
        let http = Client::builder()
            .timeout(Duration::from_secs(180))
            .build()
            .context("build image helper client")?;
        let resp = http
            .post(url)
            .json(req)
            .send()
            .await
            .context("helper POST /v1/internal/image")?;
        let status = resp.status();
        let parsed: BridgeOk = resp
            .json()
            .await
            .context("helper decode image")?;
        if !status.is_success() && parsed.error.is_none() {
            return Err(anyhow!(
                "helper image status={status} err={:?}",
                parsed.error
            ));
        }
        Ok(parsed)
    }

    async fn post_json<T: Serialize>(&self, path: &str, body: &T) -> Result<BridgeOk> {
        let url = format!("{}{}", self.base, path);
        let resp = self
            .http
            .post(url)
            .json(body)
            .send()
            .await
            .with_context(|| format!("helper POST {path}"))?;
        let status = resp.status();
        let parsed: BridgeOk = resp
            .json()
            .await
            .with_context(|| format!("helper decode {path}"))?;
        if !status.is_success() && parsed.error.is_none() {
            return Err(anyhow!(
                "helper {path} status={status} err={:?}",
                parsed.error
            ));
        }
        Ok(parsed)
    }
}
