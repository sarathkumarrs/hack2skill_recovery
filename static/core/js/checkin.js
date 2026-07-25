(function () {
  "use strict";

  function getCsrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function submitCheckin(payload, onError) {
    fetch("/checkins/create/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (data) {
            throw new Error(data.error || "Something went wrong.");
          });
        }
        return res.json();
      })
      .then(function (data) {
        window.location.href = data.redirect_url;
      })
      .catch(function (err) {
        onError(err.message || "Something went wrong. Please try again.");
      });
  }

  function setBusy(buttons, busy) {
    buttons.forEach(function (btn) {
      btn.disabled = busy;
      btn.classList.toggle("opacity-50", busy);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var moodButtons = Array.prototype.slice.call(document.querySelectorAll(".mood-btn"));
    var micButton = document.getElementById("mic-button");
    var statusEl = document.getElementById("checkin-status");
    var allInteractive = moodButtons.concat(micButton ? [micButton] : []);

    function showStatus(text, isError) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.classList.toggle("text-red-600", !!isError);
      statusEl.classList.toggle("text-slate-500", !isError);
    }

    // --- One-tap mood check-in (<3s: immediate submit on tap) ---
    moodButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        setBusy(allInteractive, true);
        showStatus("Checking in…", false);
        submitCheckin({ mood: btn.dataset.mood }, function (message) {
          setBusy(allInteractive, false);
          showStatus(message, true);
        });
      });
    });

    // --- Hold-to-talk voice check-in ---
    if (!micButton) return;

    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      // Fallback: swap the mic button for a plain textarea + submit button.
      var fallback = document.createElement("div");
      fallback.className = "w-full max-w-xs flex flex-col gap-2";
      fallback.innerHTML =
        '<textarea id="voice-fallback-text" rows="3" placeholder="Type how you\'re feeling…" ' +
        'class="w-full rounded-lg border border-slate-300 p-3 text-base"></textarea>' +
        '<button type="button" id="voice-fallback-submit" ' +
        'class="rounded-xl bg-brand-700 text-white font-semibold py-3">Submit</button>';
      micButton.replaceWith(fallback);

      document.getElementById("voice-fallback-submit").addEventListener("click", function () {
        var text = document.getElementById("voice-fallback-text").value.trim();
        if (!text) return;
        setBusy(moodButtons, true);
        showStatus("Sending…", false);
        submitCheckin({ voice_transcript: text }, function (message) {
          setBusy(moodButtons, false);
          showStatus(message, true);
        });
      });
      return;
    }

    var recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    var transcriptParts = [];
    var listening = false;

    recognition.onresult = function (event) {
      for (var i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          transcriptParts.push(event.results[i][0].transcript);
        }
      }
    };

    recognition.onerror = function () {
      listening = false;
      showStatus("Couldn't hear you — try again.", true);
    };

    recognition.onend = function () {
      if (!listening) return; // already handled by stopListening()
      listening = false;
      finishRecording();
    };

    function startListening() {
      transcriptParts = [];
      listening = true;
      showStatus("Listening… release to send", false);
      try {
        recognition.start();
      } catch (e) {
        /* already started — ignore */
      }
    }

    function stopListening() {
      if (!listening) return;
      listening = false;
      recognition.stop();
      finishRecording();
    }

    function finishRecording() {
      var transcript = transcriptParts.join(" ").trim();
      if (!transcript) {
        showStatus("Didn't catch that — hold the button and try again.", true);
        return;
      }
      setBusy(allInteractive, true);
      showStatus("Sending…", false);
      submitCheckin({ voice_transcript: transcript }, function (message) {
        setBusy(allInteractive, false);
        showStatus(message, true);
      });
    }

    micButton.addEventListener("mousedown", startListening);
    micButton.addEventListener("touchstart", function (e) {
      e.preventDefault();
      startListening();
    });
    micButton.addEventListener("mouseup", stopListening);
    micButton.addEventListener("mouseleave", stopListening);
    micButton.addEventListener("touchend", stopListening);
  });
})();
