/*
 * Shared M-Pesa STK-push logic for every payment surface (payment_required.html,
 * paywall_overlay.html, the calculator gate and the AI-chat top-up modal).
 * The state machine (phone normalisation, STK push, status polling, recovery) lives
 * here once; each template keeps its own look via the callbacks/config passed in.
 *
 * Recovery built in, so a user who paid is never left stuck:
 *  - a 409 "already in progress" resumes polling that payment instead of erroring;
 *  - when polling runs out, we ask M-Pesa directly (verify endpoint) before showing
 *    the timeout panel;
 *  - coming back to the tab (after approving in the M-Pesa app) re-checks at once.
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

    var poll, dotsTimer, currentPaymentId = null, polling = false, finished = false;

    // Accept 0712345678, 0112345678, +254712345678, 254712345678 or 712345678 — returns 9 digits or null
    function normalizePhone(input) {
        var digits = (input || '').replace(/\D/g, '');
        if (digits.length === 9 && /^[17]/.test(digits)) return digits;
        if (digits.length === 10 && /^0[17]/.test(digits)) return digits.slice(1);
        if (digits.length === 12 && /^254[17]/.test(digits)) return digits.slice(3);
        return null;
    }

    function clear() {
        if (poll) clearInterval(poll);
        if (dotsTimer) clearInterval(dotsTimer);
        poll = dotsTimer = null;
        polling = false;
    }

    function succeed() {
        if (finished) return;
        finished = true;
        clear();
        onSuccess();
    }

    async function checkOnce() {
        var sr = await fetch('/payments/status/' + currentPaymentId + '/', { credentials: 'same-origin' });
        var sd = await sr.json();
        return sd.status;
    }

    function startPolling(paymentId) {
        clear();
        finished = false;
        currentPaymentId = paymentId;
        polling = true;
        stateFn('waiting');
        var attempts = 0;
        dotsTimer = setInterval(onDots, 500);
        poll = setInterval(async function () {
            attempts++;
            try {
                var status = await checkOnce();
                if (status === 'completed') { succeed(); return; }
                if (status === 'failed') { clear(); stateFn('failed'); onFailed(); return; }
            } catch (e) { /* flaky mobile data — keep trying */ }
            if (attempts >= MAX_ATTEMPTS) {
                clear();
                // Last resort before "timed out": ask M-Pesa directly.
                verifyById(paymentId, { quiet: true });
                onTimeout();
            }
        }, 3000);
    }

    // User approved in the M-Pesa app and came back — check immediately.
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState !== 'visible' || !polling || !currentPaymentId) return;
        checkOnce().then(function (status) { if (status === 'completed') succeed(); }).catch(function(){});
    });

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
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
                body: JSON.stringify({ feature: FEATURE, phone: '0' + raw })
            });
            var d = {};
            try { d = await res.json(); } catch (e) { /* non-JSON error page */ }
            if (d.success) {
                startPolling(d.payment_id);
                (hooks.onInitiated || function(){})(d);
            } else if (d.already_unlocked) {
                (hooks.onAlreadyUnlocked || function(){ window.location.reload(); })();
            } else if (res.status === 409 && d.payment_id) {
                (hooks.onResumePending || function(){})(d.payment_id, d.message);
                startPolling(d.payment_id);
            } else if (res.status === 403) {
                (hooks.onError || function(){})('Your session expired. Please refresh the page and try again.');
            } else {
                (hooks.onError || function(){})(d.message || 'Something went wrong. No money was taken — please try again.');
            }
        } catch (e) {
            (hooks.onError || function(){})('Network error. Check your internet connection and try again.');
        }
    }

    async function verifyById(paymentId, hooks) {
        hooks = hooks || {};
        if (!hooks.quiet) stateFn('checking');
        try {
            var r = await fetch('/payments/verify/' + paymentId + '/', { credentials: 'same-origin' });
            var d = await r.json();
            if (d.status === 'completed') {
                succeed();
            } else if (d.status === 'failed') {
                stateFn('failed');
                onFailed(d.message);
                (hooks.onFailedMessage || function(){})(d.message);
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

/*
 * "I already paid" — submit an M-Pesa code (or the whole SMS). Resolves to the
 * server's JSON: { status: 'completed'|'under_review'|'not_found'|'error', message }.
 */
async function submitMpesaCode(url, csrfToken, feature, code) {
    try {
        var r = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ feature: feature, mpesa_code: code })
        });
        var d = {};
        try { d = await r.json(); } catch (e) {}
        if (r.status === 403) return { status: 'error', message: 'Your session expired. Please refresh the page and try again.' };
        return d.status ? d : { status: 'error', message: 'Something went wrong. Please try again.' };
    } catch (e) {
        return { status: 'error', message: 'Network error. Check your internet connection and try again.' };
    }
}
