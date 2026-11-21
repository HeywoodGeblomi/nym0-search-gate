//! Ownership gate borrowed from agent_action_gate_rust_v2: an action is emitted only
//! through emit(), which requires ExclusiveIntent<T: SafeTool>. FireWeapon implements
//! Tool but not SafeTool, so a typed emit of it does not compile.
//! Runtime tool names still go through the written policy and sandbox::emit.

pub trait Tool { const NAME: &'static str; }
pub trait SafeTool: Tool {}

pub struct ExclusiveIntent<T: Tool> { _t: std::marker::PhantomData<T> }
impl<T: Tool> ExclusiveIntent<T> {
    fn new() -> Self { ExclusiveIntent { _t: std::marker::PhantomData } }
}

pub struct Noop;
impl Tool for Noop { const NAME: &'static str = "noop"; }
impl SafeTool for Noop {}

pub struct FireWeapon;
impl Tool for FireWeapon { const NAME: &'static str = "dangerous_fire_weapon"; }
// FireWeapon does not implement SafeTool.

/// The only way to mint an ExclusiveIntent for a SafeTool in this crate (private constructor).
pub fn try_own_noop() -> ExclusiveIntent<Noop> { ExclusiveIntent::new() }

/// Takes the intent by value (it is moved). Cannot emit twice with the same intent.
pub fn emit<T: SafeTool>(_intent: ExclusiveIntent<T>) -> &'static str { T::NAME }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn emit_noop_once() {
        let i = try_own_noop();
        assert_eq!(emit(i), "noop");
        // i has been moved; a second emit(i) would not compile.
    }
}
