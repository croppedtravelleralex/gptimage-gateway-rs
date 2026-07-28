//! Rust upstream data plane — ported from `gptimage-panda` (primary) with
//! `../gptimage` cross-check for intentional drift.
//!
//! Phase 1 scope: TLS client, PoW, Turnstile VM, SSE parsing, chat-requirements.

pub mod account;
pub mod conversation;
pub mod pow;
pub mod requirements;
pub mod sentinel;
pub mod sse;
pub mod tls;
pub mod turnstile;

pub use account::PinAccount;
pub use requirements::{ChatRequirements, RequirementsClient};
pub use sse::{ConversationState, ImageSseReady, SseEvent, SseParser, TextSseReady};
