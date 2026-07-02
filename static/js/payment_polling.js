/*
 * Shared M-Pesa STK-push polling logic for payment_required.html and
 * paywall_overlay.html. Both templates had near-identical copies of this
 * state machine (phone normalisation, STK push initiation, status polling,
 * panel switching) — kept here once so a fix to the polling loop doesn't
 * need to be made twice. Success handling, manual-code entry and other
 * per-template UX stay in the templates via the callbacks/config passed in.
 */
function createPaymentPoller(config) {
    var FEATURE = config.feature;
    var INITIATE_URL = config.initiateUrl;
    var CSRF = config.csrfToken;
    var MAX_ATTEMPTS = config.maxAttempts || 40; // default: 40 x 3s = 2 minutes
    var onSuccess = config.onSuccess || function(){};
    var onFailed = config.onFailed || function(){};
    var onTimeout = config.onTimeout || function(){};
    var onDots = config.onDots || function(){};
    var stateFn = config.state;

    var poll, dotsTimer, currentPaymentId = null;

    // Accept 0712345678, +254712345678, 254712345678 or plain 712345678 — always returns 9 digits or null
    function normalizePhone(input) {
        var digits = (input || '').replace(/\D/g, '');
        if (digits.length === 9 && /^[17]/.test(digits)) return digits;
        if (digits.length === 10 && digits.startsWith('0')) return digits.slice(1);
        if (digits.length === 12 && digits.startsWith('254')) return digits.slice(3);
        return null;
    }

    function clear() {
        if (poll) clearInterval(poll);
        if (dotsTimer) clearInterval(dotsTimer);
    }

    function startPolling(paymentId) {
        currentPaymentId = paymentId;
        stateFn('waiting');
        var attempts = 0;
        dotsTimer = setInterval(onDots, 500);
        poll = setInterval(async function () {
            attempts++;
            try {
                var sr = await fetch('/payments/status/' + paymentId + '/');
                var sd = await sr.json();
                if (sd.status === 'completed') { clear(); onSuccess(); }
                else if (sd.status === 'failed') { clear(); stateFn('failed'); onFailed(); }
                else if (attempts >= MAX_ATTEMPTS) { clear(); stateFn('timeout'); onTimeout(); }
            } catch (e) {
                if (attempts >= MAX_ATTEMPTS) { clear(); stateFn('timeout'); onTimeout(); }
            }
        }, 3000);
    }

    async function pay(rawPhone, hooks) {
        hooks = hooks || {};
        var raw = normalizePhone(rawPhone);
        if (!raw) {
            (hooks.onInvalidPhone || function(){})();
            return;
        }
        (hooks.onSending || function(){})();
        try {
            var res = await fetch(INITIATE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
                body: JSON.stringify({ feature: FEATURE, phone: '0' + raw })
            });
            var d = await res.json();
            if (d.success) {
                startPolling(d.payment_id);
                (hooks.onInitiated || function(){})(d);
            } else if (hooks.onAlreadyUnlocked && res.status === 400 && d.message && d.message.indexOf('already unlocked') !== -1) {
                hooks.onAlreadyUnlocked();
            } else if (hooks.onResumePending && res.status === 409 && d.payment_id) {
                hooks.onResumePending(d.payment_id);
                startPolling(d.payment_id);
            } else {
                (hooks.onError || function(){})(d.message || 'Something went wrong. Please try again.');
            }
        } catch (e) {
            (hooks.onError || function(){})('Network error. Check your connection and try again.');
        }
    }

    async function verifyById(paymentId, hooks) {
        hooks = hooks || {};
        stateFn('checking');
        try {
            var r = await fetch('/payments/verify/' + paymentId + '/');
            var d = await r.json();
            if (d.status === 'completed') {
                onSuccess();
            } else if (d.status === 'failed') {
                stateFn('failed');
                onFailed();
            } else {
                stateFn('timeout');
                (hooks.onStillPending || function(){})(d.message);
            }
        } catch (e) {
            stateFn('timeout');
            (hooks.onNetworkError || function(){})();
        }
    }

    return {
        normalizePhone: normalizePhone,
        pay: pay,
        startPolling: startPolling,
        verifyById: verifyById,
        clear: clear,
        getCurrentPaymentId: function () { return currentPaymentId; },
        setCurrentPaymentId: function (id) { currentPaymentId = id; }
    };
}
