//! Gateway adapter for the Rust upstream data plane.

use anyhow::Result;
use helper_client::PinAccount as HelperPinAccount;
use upstream::{PinAccount as UpstreamPinAccount, UpstreamRuntime};

fn to_upstream(account: &HelperPinAccount) -> UpstreamPinAccount {
    UpstreamPinAccount {
        email: account.email.clone(),
        access_token: account.access_token.clone(),
        device_id: account.device_id.clone().unwrap_or_default(),
        proxy: account.proxy.clone().unwrap_or_default(),
        user_agent: account.user_agent.clone().unwrap_or_default(),
        impersonate: String::new(),
    }
}

pub async fn run_text(account: &HelperPinAccount, prompt: String, model: String) -> Result<String> {
    let mut runtime = UpstreamRuntime::new(to_upstream(account))?;
    runtime.run_text(&prompt, &model).await
}

pub async fn run_image(
    account: &HelperPinAccount,
    prompt: String,
    model: String,
) -> Result<Vec<u8>> {
    let mut runtime = UpstreamRuntime::new(to_upstream(account))?;
    runtime.run_image(&prompt, &model).await
}
