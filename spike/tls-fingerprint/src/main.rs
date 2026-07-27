//! Phase B' spike: does `wreq` + `wreq-util` reproduce the TLS fingerprint that
//! Python's `curl_cffi` impersonate produces?
//!
//! Production Python uses impersonate profiles chrome120 / chrome124 / chrome131
//! (gptimage-panda `services/account_fingerprint.py` FP_PROFILES). This drives
//! the matching wreq-util presets against a JA3/JA4 reflection service and
//! prints the raw fields for byte-level diffing against the Python baseline.

use std::time::Duration;

use wreq::Client;
use wreq_util::{Emulation, Platform, Profile};

/// JA3/JA4 reflection endpoint. Overridable: these services come and go.
fn fp_endpoint() -> String {
    std::env::var("FP_ENDPOINT")
        .unwrap_or_else(|_| "https://tls.browserleaks.com/json".to_string())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let proxy = std::env::var("SPIKE_PROXY").ok().filter(|p| !p.is_empty());

    // Mirrors the curl_cffi impersonate values used in production. curl_cffi's
    // chrome* profiles report a macOS user agent, so pin the same platform —
    // otherwise the UA differs and the comparison is not like-for-like.
    let targets: Vec<(&str, Profile)> = vec![
        ("chrome120", Profile::Chrome120),
        ("chrome124", Profile::Chrome124),
        ("chrome131", Profile::Chrome131),
        
        
    ];

    let endpoint = fp_endpoint();
    println!("endpoint: {endpoint}");
    let mut results = Vec::new();

    for (label, profile) in targets {
        let emulation = Emulation::builder()
            .profile(profile)
            .platform(Platform::MacOS)
            .http2(true)
            .build();

        let mut builder = Client::builder()
            .emulation(emulation)
            .timeout(Duration::from_secs(30));

        if let Some(url) = proxy.as_deref() {
            builder = builder.proxy(wreq::Proxy::all(url)?);
        }

        let client = builder.build()?;

        match client.get(&endpoint).header("accept", "application/json").send().await {
            Ok(resp) => {
                let status = resp.status();
                let hdrs: Vec<String> = resp.headers().iter().map(|(k,v)| format!("{k}: {}", v.to_str().unwrap_or("?"))).collect();
                println!("HEADERS: {hdrs:?}");
                let body = resp.text().await?;
                println!("BODY_LEN: {}", body.len());
                std::fs::write(format!("out-{label}.json"), &body).ok();
                println!("=== wreq {label} (HTTP {status}) ===");
                println!("{body}");
                println!();
                match serde_json::from_str::<serde_json::Value>(&body) {
                    Ok(parsed) => results.push((label.to_string(), parsed)),
                    Err(e) => println!("(non-JSON body: {e})"),
                }
            }
            Err(e) => {
                println!("=== wreq {label} FAILED ===");
                println!("{e}");
                println!();
            }
        }
    }

    println!("---SUMMARY-JSON---");
    let summary: Vec<_> = results
        .into_iter()
        .map(|(label, v)| {
            serde_json::json!({
                "client": "wreq",
                "profile": label,
                "ja3_hash": v.get("ja3_hash"),
                "ja3_text": v.get("ja3_text"),
                "ja3n_hash": v.get("ja3n_hash"),
                "ja4": v.get("ja4"),
                "ja4_r": v.get("ja4_r"),
                "ja4_ro": v.get("ja4_ro"),
                "akamai_hash": v.get("akamai_hash"),
                "akamai_text": v.get("akamai_text"),
                "user_agent": v.get("user_agent"),
            })
        })
        .collect();
    println!("{}", serde_json::to_string_pretty(&summary)?);

    Ok(())
}
