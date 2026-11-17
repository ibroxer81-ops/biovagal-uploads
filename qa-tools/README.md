# Mistake scanner

`python3 qa.py [--fix] DIR [DIR ...]`

Checks: known typos, doubled words, brand spelling (Biovagal, Punsnup), "Headphones required" rule,
Greenock mentions, health/outcome claims on Biovagal, old £2.99 price, test-mode or unknown Stripe links,
broken internal links, missing titles, and a list of unknown words to review.
`--fix` applies only safe fixes (typo list, doubled words, brand case, Headphones wording).
Add project words to whitelist.txt.
