(function () {
  var script = document.currentScript;
  var businessId = script && script.getAttribute("data-business");
  var origin = new URL(script.src).origin;
  var sessionId = "w_" + Math.random().toString(36).slice(2);
  if (!businessId) return;

  var open = false;
  var style = document.createElement("style");
  style.textContent =
    ".lbz-btn{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;background:#D6B76C;border:none;cursor:pointer;box-shadow:0 8px 32px rgba(0,0,0,.4);z-index:999999;display:flex;align-items:center;justify-content:center;font-size:26px}" +
    ".lbz-box{position:fixed;bottom:96px;right:24px;width:360px;max-width:92vw;height:520px;max-height:72vh;background:#0B0D12;border:1px solid rgba(214,183,108,.3);border-radius:16px;z-index:999999;display:none;flex-direction:column;overflow:hidden;font-family:system-ui,sans-serif;box-shadow:0 20px 60px rgba(0,0,0,.6)}" +
    ".lbz-box.open{display:flex}" +
    ".lbz-hd{padding:16px;border-bottom:1px solid rgba(214,183,108,.2);color:#F5F1E8;font-weight:600}" +
    ".lbz-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}" +
    ".lbz-m{max-width:80%;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.4}" +
    ".lbz-u{align-self:flex-end;background:#D6B76C;color:#0B0D12}" +
    ".lbz-a{align-self:flex-start;background:#171A21;color:#e2e8f0;border:1px solid rgba(214,183,108,.15)}" +
    ".lbz-in{display:flex;padding:12px;gap:8px;border-top:1px solid rgba(214,183,108,.2)}" +
    ".lbz-in input{flex:1;background:#171A21;border:1px solid rgba(214,183,108,.2);border-radius:8px;padding:8px 12px;color:#fff;outline:none}" +
    ".lbz-in button{background:#D6B76C;border:none;border-radius:8px;padding:0 14px;cursor:pointer;color:#0B0D12;font-weight:600}" +
    ".lbz-cs{display:flex;flex-wrap:wrap;gap:4px 14px;padding:0 12px 10px;font-size:11px;color:#89919E}.lbz-cs label{display:flex;align-items:center;gap:4px;cursor:pointer}.lbz-cs input{accent-color:#D6B76C}.lbz-m{white-space:pre-line}";
  document.head.appendChild(style);

  var btn = document.createElement("button");
  btn.className = "lbz-btn";
  btn.innerHTML = "\uD83D\uDCAC";

  var box = document.createElement("div");
  box.className = "lbz-box";
  box.innerHTML =
    '<div class="lbz-hd">Assistant<div style="font-size:10px;letter-spacing:.2em;color:#89919E;font-weight:500;margin-top:4px">POWERED BY VANTORA AI</div></div><div class="lbz-msgs"><div class="lbz-m lbz-a">Hi! How can I help you today?</div></div>' +
    '<div class="lbz-in"><input placeholder="Type a message..."/><button>Send</button></div>' +
    '<div class="lbz-cs"><label><input type="checkbox" data-consent="email"/> Email me offers &amp; updates</label><label><input type="checkbox" data-consent="sms"/> Text me offers &amp; updates</label><span>(optional)</span></div>';

  document.body.appendChild(btn);
  document.body.appendChild(box);
  var msgs = box.querySelector(".lbz-msgs");
  var input = box.querySelector(".lbz-in input");
  var send = box.querySelector(".lbz-in button");
  function consent() {
    var c = {};
    box.querySelectorAll("[data-consent]").forEach(function (el) { if (el.checked) c[el.getAttribute("data-consent")] = true; el.checked = false; });
    return c;
  }

  btn.onclick = function () { open = !open; box.classList.toggle("open", open); };

  function add(cls, text) {
    var d = document.createElement("div");
    d.className = "lbz-m " + cls;
    d.textContent = text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  async function submit() {
    var t = input.value.trim();
    if (!t) return;
    input.value = "";
    add("lbz-u", t);
    var a = add("lbz-a", "...");
    try {
      var res = await fetch(origin + "/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: t, business_id: businessId, consent: consent() }),
      });
      if (!res.ok) { a.textContent = "Chat is currently unavailable."; return; }
      var reader = res.body.getReader();
      var dec = new TextDecoder();
      var acc = "";
      while (true) {
        var r = await reader.read();
        if (r.done) break;
        acc += dec.decode(r.value, { stream: true });
        a.textContent = acc;
        msgs.scrollTop = msgs.scrollHeight;
      }
    } catch (e) { a.textContent = "Something went wrong."; }
  }

  send.onclick = submit;
  input.addEventListener("keydown", function (e) { if (e.key === "Enter") submit(); });
})();
