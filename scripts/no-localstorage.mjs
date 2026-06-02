// Node 25 ships a non-functional localStorage stub by default that breaks
// SSR for libs guarding on `typeof localStorage !== 'undefined'`. Wipe it.
delete globalThis.localStorage;
delete globalThis.sessionStorage;
