const message = document.getElementById("message");
const signIn = document.getElementById("sign-in");
const enroll = document.getElementById("enroll");

function fromBase64url(value) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="));
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}
function toBase64url(value) {
  const bytes = new Uint8Array(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
async function post(path, data) {
  const response = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", cache: "no-store", body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "認証できませんでした");
  return result;
}
function optionsForBrowser(options, creating) {
  const key = options.publicKey;
  key.challenge = fromBase64url(key.challenge);
  if (creating) {
    key.user.id = fromBase64url(key.user.id);
    for (const item of key.excludeCredentials || []) item.id = fromBase64url(item.id);
  } else {
    for (const item of key.allowCredentials || []) item.id = fromBase64url(item.id);
  }
  return key;
}
function credentialJSON(credential, creating) {
  const response = credential.response;
  return {
    id: credential.id, type: credential.type, rawId: toBase64url(credential.rawId),
    response: creating
      ? { clientDataJSON: toBase64url(response.clientDataJSON), attestationObject: toBase64url(response.attestationObject), transports: response.getTransports?.() || [] }
      : { clientDataJSON: toBase64url(response.clientDataJSON), authenticatorData: toBase64url(response.authenticatorData), signature: toBase64url(response.signature), userHandle: response.userHandle ? toBase64url(response.userHandle) : null },
  };
}
async function run(kind) {
  if (!window.PublicKeyCredential || !navigator.credentials) throw new Error("このブラウザは端末認証に対応していません");
  const creating = kind === "enroll";
  const code = document.getElementById("code").value.trim();
  if (creating && !code) throw new Error("登録コードを入力してください");
  const begin = await post(`/auth/${kind}/begin`, creating ? {code} : {});
  const publicKey = optionsForBrowser(begin.options, creating);
  const credential = creating
    ? await navigator.credentials.create({publicKey})
    : await navigator.credentials.get({publicKey});
  if (!credential) throw new Error("端末の確認がキャンセルされました");
  await post(`/auth/${kind}/complete`, {flow: begin.flow, credential: credentialJSON(credential, creating)});
  location.replace("/");
}
async function attempt(kind) {
  signIn.disabled = enroll.disabled = true;
  message.textContent = "端末を確認しています…";
  try {
    await run(kind);
  } catch (error) {
    message.textContent = error.name === "NotAllowedError" ? "端末の確認がキャンセルされました" : error.message;
  } finally {
    signIn.disabled = enroll.disabled = false;
  }
}
signIn.addEventListener("click", () => attempt("login"));
enroll.addEventListener("click", () => attempt("enroll"));
