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
    var statusEl = document.getElementById("checkin-status");

    function showStatus(text, isError) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.classList.toggle("text-red-600", !!isError);
      statusEl.classList.toggle("text-slate-500", !isError);
    }

    // --- One-tap mood check-in (<3s: immediate submit on tap) ---
    moodButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        setBusy(moodButtons, true);
        showStatus("Checking in…", false);
        submitCheckin({ mood: btn.dataset.mood }, function (message) {
          setBusy(moodButtons, false);
          showStatus(message, true);
        });
      });
    });
  });
})();
