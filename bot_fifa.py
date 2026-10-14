"""
Bot Telegram d'analyse de matchs FIFA (e-soccer) - v1, cotes saisies à la main.

Installation :
    pip install "python-telegram-bot>=20"
Lancement :
    export TELEGRAM_TOKEN="le_token_donné_par_BotFather"
    python bot_fifa.py

Commande :
    /analyse JoueurA JoueurB coteA coteNul coteB A_marqués A_encaissés B_marqués B_encaissés
Exemple :
    /analyse Barcelona Madrid 2.10 4.20 3.00 3.2 2.1 2.8 2.6
(les 4 derniers nombres = moyennes de buts sur les derniers matchs de chaque joueur)
"""
import math
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

EDGE_MIN = 0.05        # écart minimum (5 points) pour signaler une "value"
KELLY_FRACTION = 0.25  # on ne mise qu'un quart du Kelly, par prudence
MAX_GOALS = 12


def poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def probs_1x2(lam_a: float, lam_b: float):
    """Probabilités victoire A / nul / victoire B avec un modèle de Poisson."""
    pa = pd = pb = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = poisson(i, lam_a) * poisson(j, lam_b)
            if i > j:
                pa += p
            elif i == j:
                pd += p
            else:
                pb += p
    total = pa + pd + pb
    return pa / total, pd / total, pb / total


def sans_marge(cotes):
    """Probabilités implicites des cotes, marge du bookmaker retirée."""
    inv = [1 / c for c in cotes]
    s = sum(inv)
    return [x / s for x in inv], s - 1


def kelly(p: float, cote: float) -> float:
    f = (p * cote - 1) / (cote - 1)
    return max(0.0, f * KELLY_FRACTION)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Utilisation :\n"
        "/analyse A B coteA coteNul coteB A_marqués A_encaissés B_marqués B_encaissés\n\n"
        "Exemple :\n/analyse Barcelona Madrid 2.10 4.20 3.00 3.2 2.1 2.8 2.6"
    )


async def analyse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 9:
        await update.message.reply_text("Format invalide. Tape /start pour voir l'exemple.")
        return
    try:
        a, b = args[0], args[1]
        c1, cx, c2, a_for, a_ag, b_for, b_ag = (float(x.replace(",", ".")) for x in args[2:])
    except ValueError:
        await update.message.reply_text("Les cotes et moyennes doivent être des nombres.")
        return
    if min(c1, cx, c2) <= 1:
        await update.message.reply_text("Les cotes doivent être supérieures à 1.")
        return

    lam_a = max(0.1, (a_for + b_ag) / 2)
    lam_b = max(0.1, (b_for + a_ag) / 2)
    modele = probs_1x2(lam_a, lam_b)
    cotes = [c1, cx, c2]
    book, marge = sans_marge(cotes)
    noms = [f"Victoire {a}", "Match nul", f"Victoire {b}"]

    lignes = [f"⚽ {a} vs {b}", f"Marge du bookmaker : {marge * 100:.1f}%", ""]
    values = []
    for nom, cote, pm, pb_ in zip(noms, cotes, modele, book):
        ecart = pm - pb_
        flag = ""
        if ecart > EDGE_MIN and pm * cote > 1:
            flag = " ✅ VALUE"
            values.append((nom, cote, kelly(pm, cote)))
        lignes.append(
            f"{nom} @ {cote}\n  modèle {pm * 100:.1f}% | cotes {pb_ * 100:.1f}% | écart {ecart * 100:+.1f}{flag}"
        )
    lignes.append("")
    if values:
        for nom, cote, f in values:
            lignes.append(f"👉 {nom} @ {cote} : mise suggérée {f * 100:.1f}% de la bankroll")
    else:
        lignes.append("Aucune value détectée : mieux vaut passer ce match.")
    lignes.append("\n⚠️ Estimation statistique, pas une garantie de gain.")
    await update.message.reply_text("\n".join(lignes))


def main():
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyse", analyse))
    app.run_polling()


if __name__ == "__main__":
    main()
