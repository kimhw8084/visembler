# CHG-253 R2 evidence

Candidate 8a2539a50ed7d4d638baa52e1574dafbf5527478 (tree bcff2aeab48bfc4d6ca2f0105365030d7a9ff992) is based on exact target main 353d8c648be0d88db2777f68e577a4ec47d8a6bb. R1 accepted head 3777fa759c96355888ea3a39715693ab4f306667 is its direct parent. The one-file delta removes the implicit historical screenshot read from regression output packaging. R1 Product CSS/MJS, certification manifest, and CHG-207/209 regression files retain their exact blobs.

The R1 depth-1 reproduction and PR #27 run #283 traceback are under reproduction/ and ci/. R2 focused and full pytest results come from a new Python 3.12.9 shallow clone. The focused run recorded zero Git subprocess invocations. Native Preview output and candidate screenshots are under native-acceptance/. The R1 historical visual baseline is linked immutably in screenshots/manifest.json.

The maintained native release verifier report and required gate evidence are under release/. Result: PASS_LOCAL_INTERNAL_PILOT; managed target status remains PENDING.
