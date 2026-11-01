"use strict";

// Keep confirmation behavior in an external script so CSP can block inline JS.
document.addEventListener("submit", function (event) {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
