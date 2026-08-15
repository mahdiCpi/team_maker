## Code and Test Organization
 
### Meaningful Structure

- Avoid flat file organization as the project grows. Organize code and tests by meaningful domain, component, feature, or responsibility.

- Do not create artificial directories prematurely. A small module or early story may remain simple until enough related files/tests exist to justify separation.

- Structure must evolve with the project. A layout that is reasonable for Story 1.1 may need to be reorganized when Stories 1.2, 1.3, etc. add significant functionality.
 
### Test Organization

- Do not accumulate unrelated test functions in one large test file.

- Separate test functions into meaningful test files based on the component, behavior, feature, or responsibility being tested.

- As the number of test files grows, group them into meaningful directories, preferably corresponding to the source/domain structure.

- Do not create nearly empty directories merely to mirror `src`; introduce subdirectories when they provide meaningful organization.

- When a new story causes an existing test area to become crowded or flat, reorganize the existing tests as part of that story rather than continuing to add files to the root.

- Prefer pytest test functions. Use test classes only when they provide a clear benefit.
 
Example evolution:
 
Story 1.1 may reasonably start as:
 
tests/

  test_execution.py

  test_validation.py
 
As later stories expand the project, evolve it into:
 
tests/

  execution/

    test_orders.py

    test_fills.py

    test_validation.py

  strategy/

    test_signals.py

    test_indicators.py
 
The goal is meaningful separation and discoverability, not directory creation for its own sake.
 
### Test Transparency

- Clearly identify mocks, stubs, fakes, monkeypatches, synthetic data, simulated services, skipped tests, and other non-real behavior.

- Never report a mocked/stubbed integration as proof that the real integration works.

- When reporting test results, distinguish unit, mocked integration, local integration, sandbox/testnet, and real end-to-end tests.
 
### File Size and Modularity

- Prefer small, cohesive files with one clear responsibility.

- Approximately 200–400 lines is a review guideline, not a hard limit.

- Split large files by meaningful responsibility, not merely to satisfy a line-count limit.
 
 ## Branch Organization Rules

Ensure the `develop` branch is up to date before starting. Then follow these rules:

1. Use consistent branch names:
   - Epics: `epic_<number>` — e.g. `epic_2`.
   - Stories: `story_<epic-number>_<story-number>` — e.g. `story_1_3` (story 3 of epic 1).
2. Each epic has its own branch.
3. Each story is branched from its epic.
4. Once a story is accepted, merge it into its epic branch. Then, create the next story branch on the remote, and then checkout. 
5. Once an epic is verified working, merge it into `develop`.
6. After reviewing a branch, commit and push it to the remote repo.
7. Create every branch on the remote (not just locally) so the repo's network graph stays clean and readable.