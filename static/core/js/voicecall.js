(function () {
  "use strict";

  function getCsrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var startButton = document.getElementById("start-call-button");
    if (!startButton) return;

    var callPanel = document.getElementById("call-panel");
    var callStatus = document.getElementById("call-status");
    var hangupButton = document.getElementById("hangup-button");

    var callFrame = null;
    var sessionId = null;
    var leaving = false;

    function setStatus(text) {
      if (callStatus) callStatus.textContent = text;
    }

    function showPanel() {
      if (callPanel) callPanel.classList.remove("hidden");
    }

    function hidePanel() {
      if (callPanel) callPanel.classList.add("hidden");
    }

    function showFallback(message) {
      setStatus(message);
      hangupButton.textContent = "Back to Home";
      hangupButton.onclick = function () {
        window.location.href = "/home/";
      };
    }

    function pollStatus(attemptsLeft) {
      if (attemptsLeft <= 0) {
        showFallback("Still wrapping up — check your check-in history in a moment.");
        return;
      }
      fetch("/voicecalls/" + sessionId + "/status/")
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.status === "completed") {
            window.location.href = data.redirect_url;
          } else if (data.status === "failed") {
            showFallback("Your check-in couldn't be completed this time.");
          } else {
            setTimeout(function () {
              pollStatus(attemptsLeft - 1);
            }, 1000);
          }
        })
        .catch(function () {
          setTimeout(function () {
            pollStatus(attemptsLeft - 1);
          }, 1000);
        });
    }

    function endCall() {
      if (leaving) return;
      leaving = true;
      setStatus("Wrapping up…");
      hangupButton.disabled = true;
      if (callFrame) {
        callFrame.leave().catch(function () {});
      }
      pollStatus(20);
    }

    hangupButton.addEventListener("click", endCall);

    startButton.addEventListener("click", function () {
      if (typeof DailyIframe === "undefined") {
        setStatus("Voice calling isn't available in this browser right now.");
        showPanel();
        return;
      }

      startButton.disabled = true;
      showPanel();
      setStatus("Connecting…");
      hangupButton.disabled = false;
      hangupButton.textContent = "End Call";
      leaving = false;

      fetch("/voicecalls/start/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
      })
        .then(function (res) {
          if (!res.ok) {
            return res.json().then(function (data) {
              throw new Error(data.error || "Couldn't start the call.");
            });
          }
          return res.json();
        })
        .then(function (data) {
          sessionId = data.session_id;
          callFrame = DailyIframe.createCallObject();

          callFrame.on("joined-meeting", function () {
            setStatus("Connected — say hello");
          });
          callFrame.on("left-meeting", function () {
            if (!leaving) endCall();
          });
          callFrame.on("error", function () {
            setStatus("Call connection error.");
          });

          return callFrame.join({ url: data.room_url, token: data.user_token });
        })
        .catch(function (err) {
          showFallback(err.message || "Couldn't start the call. Please try again.");
        })
        .finally(function () {
          startButton.disabled = false;
        });
    });
  });
})();
