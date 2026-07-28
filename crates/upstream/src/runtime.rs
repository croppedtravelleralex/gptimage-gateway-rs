use std::time::Duration;

use anyhow::{bail, Context, Result};
use tracing::info;

use crate::account::PinAccount;
use crate::conversation::{build_text_chat_body, DEFAULT_TIMEZONE};
use crate::estuary::{download_image_bytes, get_attachment_download_url, get_file_download_url};
use crate::requirements::{RequirementsClient, BASE_URL};
use crate::sentinel::build_chat_headers;
use crate::sse::{consume_sse_until, ImageSseReady, SseConsumeMode};

const DEFAULT_TEXT_SSE_TIMEOUT_SECS: u64 = 120;
const DEFAULT_IMAGE_SSE_TIMEOUT_SECS: u64 = 300;

/// End-to-end upstream runtime: requirements → conversation SSE → estuary download.
pub struct UpstreamRuntime {
    client: RequirementsClient,
    text_sse_timeout: Duration,
    image_sse_timeout: Duration,
}

impl UpstreamRuntime {
    pub fn new(account: PinAccount) -> Result<Self> {
        Ok(Self {
            client: RequirementsClient::new(account)?,
            text_sse_timeout: Duration::from_secs(DEFAULT_TEXT_SSE_TIMEOUT_SECS),
            image_sse_timeout: Duration::from_secs(DEFAULT_IMAGE_SSE_TIMEOUT_SECS),
        })
    }

    pub fn client(&self) -> &RequirementsClient {
        &self.client
    }

    pub fn client_mut(&mut self) -> &mut RequirementsClient {
        &mut self.client
    }

    /// Bootstrap → chat-requirements → text SSE → collected assistant text.
    pub async fn run_text(&mut self, prompt: &str, model: &str) -> Result<String> {
        self.client.bootstrap(true).await?;
        let requirements = self.client.fetch_chat_requirements().await?;

        let path = "/backend-api/f/conversation";
        let body = build_text_chat_body(prompt, model, DEFAULT_TIMEZONE);
        let mut headers = self.client.api_headers(path);
        headers.extend(build_chat_headers(&requirements));
        let body_str = serde_json::to_string(&body)?;

        let http = RequirementsClient::apply_headers(
            self.client
                .client()
                .post(format!("{BASE_URL}{path}"))
                .body(body_str),
            &headers,
        );
        let resp = http.send().await.context("POST /f/conversation")?;
        let status = resp.status();
        if !status.is_success() {
            let body = resp.text().await.unwrap_or_default();
            bail!(
                "conversation HTTP {status}: {}",
                &body[..body.len().min(240)]
            );
        }

        let consumed = consume_sse_until(resp, SseConsumeMode::Text, self.text_sse_timeout).await?;
        let text = consumed.parser.state().text.clone();
        info!(
            conversation_id = %consumed.parser.state().conversation_id,
            text_len = text.len(),
            events = consumed.parser.event_count(),
            "text conversation complete"
        );
        Ok(text)
    }

    /// Bootstrap → requirements → image prepare/start → SSE → estuary download.
    pub async fn run_image(&mut self, prompt: &str, model: &str) -> Result<Vec<u8>> {
        self.client.bootstrap(true).await?;
        let requirements = self.client.fetch_chat_requirements().await?;

        let conduit = self
            .client
            .prepare_image_conversation(prompt, model, &requirements)
            .await?;
        info!(conduit_len = conduit.len(), "image prepare complete");

        let resp = self
            .client
            .start_image_conversation(prompt, model, &requirements, &conduit)
            .await?;

        let consumed =
            consume_sse_until(resp, SseConsumeMode::Image, self.image_sse_timeout).await?;
        let ready = consumed
            .parser
            .image_ready()
            .context("image SSE ended without file_id")?;

        let download_url = self.resolve_image_download_url(&ready).await?;
        let access_token = self.client.account().access_token.clone();
        download_image_bytes(self.client.client(), &download_url, &access_token).await
    }

    async fn resolve_image_download_url(&self, ready: &ImageSseReady) -> Result<String> {
        const SKIP_FILE_IDS: &[&str] = &["file_upload"];

        for file_id in &ready.file_ids {
            if SKIP_FILE_IDS.contains(&file_id.as_str()) {
                continue;
            }
            let path = format!("/backend-api/files/{file_id}/download");
            let headers = self.client.api_headers(&path);
            match get_file_download_url(self.client.client(), &headers, file_id).await {
                Ok(url) if !url.is_empty() => return Ok(url),
                Ok(_) => continue,
                Err(err) => {
                    info!(%file_id, error = %err, "file download url lookup failed");
                }
            }
        }

        if !ready.conversation_id.is_empty() {
            for sediment_id in &ready.sediment_ids {
                let path = format!(
                    "/backend-api/conversation/{}/attachment/{}/download",
                    ready.conversation_id, sediment_id
                );
                let headers = self.client.api_headers(&path);
                match get_attachment_download_url(
                    self.client.client(),
                    &headers,
                    &ready.conversation_id,
                    sediment_id,
                )
                .await
                {
                    Ok(url) if !url.is_empty() => return Ok(url),
                    Ok(_) => continue,
                    Err(err) => {
                        info!(%sediment_id, error = %err, "attachment download url lookup failed");
                    }
                }
            }
        }

        bail!(
            "no image download url resolved (file_ids={:?}, sediment_ids={:?})",
            ready.file_ids,
            ready.sediment_ids
        )
    }
}
