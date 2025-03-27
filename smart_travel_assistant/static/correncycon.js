function convertCurrency() {
    let amount = document.getElementById("amount").value;
    let fromCurrency = document.getElementById("from-currency").value;
    let toCurrency = document.getElementById("to-currency").value;

    if (amount === "" || isNaN(amount) || amount <= 0) {
        document.getElementById("result").innerText = "Please enter a valid amount.";
        return;
    }

    const rates = {
        USD: { USD: 1, EUR: 0.85, INR: 74.5, GBP: 0.75, AUD: 1.35, JPY: 110.5, CAD: 1.25 },
        EUR: { USD: 1.18, EUR: 1, INR: 87.7, GBP: 0.88, AUD: 1.58, JPY: 130.0, CAD: 1.47 },
        INR: { USD: 0.013, EUR: 0.011, INR: 1, GBP: 0.010, AUD: 0.018, JPY: 1.48, CAD: 0.017 },
        GBP: { USD: 1.33, EUR: 1.14, INR: 99.2, GBP: 1, AUD: 1.80, JPY: 148.2, CAD: 1.67 },
        AUD: { USD: 0.74, EUR: 0.63, INR: 55.2, GBP: 0.56, AUD: 1, JPY: 82.3, CAD: 0.93 },
        JPY: { USD: 0.009, EUR: 0.0077, INR: 0.67, GBP: 0.0067, AUD: 0.012, JPY: 1, CAD: 0.011 },
        CAD: { USD: 0.80, EUR: 0.68, INR: 59.5, GBP: 0.60, AUD: 1.08, JPY: 89.7, CAD: 1 },
    };

    if (!(fromCurrency in rates) || !(toCurrency in rates[fromCurrency])) {
        document.getElementById("result").innerText = "Conversion rate not available.";
        return;
    }

    let convertedAmount = (amount * rates[fromCurrency][toCurrency]).toFixed(2);
    document.getElementById("result").innerText = `${amount} ${fromCurrency} = ${convertedAmount} ${toCurrency}`;
}

function updateFlag(flagId, currency) {
    const flagMap = {
        USD: 'flags/usd.png',
        EUR: 'flags/eur.png',
        INR: 'flags/inr.png',
        GBP: 'flags/gbp.png',
        AUD: 'flags/aud.png',
        JPY: 'flags/jpy.png',
        CAD: 'flags/cad.png'
    };

    const flagElement = document.getElementById(flagId);
    if (flagMap[currency]) {
        flagElement.src = flagMap[currency];
    }
}