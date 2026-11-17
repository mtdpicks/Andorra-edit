Build files for The Andorra Edit (not pages).
css/ and cssmap.json hold each page's full CSS; pages are published with only the CSS they use.
Run tools/optimize.py before every commit (all pages), or "optimize.py restore" to put the full CSS back.
tools/prune.js needs Node with css-tree 3.1.0.
