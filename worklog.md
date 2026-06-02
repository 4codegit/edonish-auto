---
Task ID: 1
Agent: Main
Task: Fix grade logic, auto-detect quarter, add signature feature, rebuild release

Work Log:
- Analyzed current codebase: main.py, grade_engine.py, api_client.py, config.py
- Identified root cause: MIN_GRADE=8 in config makes grade range 8-10, plus mark_type_id=8 was confusing
- Changed MIN_GRADE from 8 to 3, MAX_GRADE stays at 10
- Added weighted_random_grade() function with bell-curve distribution (favors 7-9, rare 3-4 and 10)
- Added auto-detection of current quarter in _detect_current_quarter() using API date ranges or month-based fallback
- Added signature feature: checkbox + text field + separate button
- Added execute_signatures() method in GradeEngine using JOURNAL_COMMENT API endpoint
- Added create_comment() method in EdonishAPI client
- Signature is applied automatically after grades when checkbox is enabled
- Bumped version to 3.2.0
- Pushed to main and created tag v3.2.0
- CI pipeline triggered successfully

Stage Summary:
- v3.2.0 pushed with all fixes
- Grade logic: weighted random 3-10 instead of uniform 8-10
- Quarter: auto-detected based on current date
- Signature: new feature to add comments/signatures to students
- CI pipeline running (#26843408474)
