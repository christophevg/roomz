# Memory: Agile Testing Philosophy

**Date**: 2026-05-14
**Project**: Roomz
**Task**: I1-001 Minimal Chat Broadcast
**Context**: Review cycle identified incomplete test stubs

## Insight

In agile project management, the focus is on developing end-to-end functionality first. Test coverage depth becomes more important when features and requirements stabilize. This "speed first, depth later" approach allows rapid iteration while maintaining quality.

## Philosophy

**Speed First, Depth Later:**
1. **Iteration 1-MVP**: Focus on working end-to-end functionality
   - Accept test stubs as executable specifications
   - Prioritize acceptance criteria verification
   - Manual verification acceptable for early iterations
   - Mark incomplete tests as `@pytest.mark.skip` with clear reason

2. **Stabilization Phase**: Increase test depth when features stabilize
   - Fill in test stubs with proper assertions
   - Add edge case tests
   - Improve coverage for critical paths

3. **Production Readiness**: Comprehensive test coverage before deployment
   - All test stubs have assertions
   - Edge cases and error paths tested
   - Integration tests for all workflows

## Critical Rule

**All tests must pass or be skipped with every commit.**

- ✅ Passing tests: Fully implemented and verified
- ✅ Skipped tests: Incomplete, marked with clear reason
- ❌ Failing tests: Never acceptable (breaks CI/CD)

**Implementation**:
- Use `@pytest.mark.skip(reason="...")` for incomplete tests
- Document why test is skipped
- All passing tests must have meaningful assertions
- No `pass` statements or `assert True` in passing tests

## Additional Lesson Learned

**Documentation Must Be Complete Before Commit**

User cannot perform acceptance testing without:
1. **README.md**: How to install, run, and test the application
2. **Setup Instructions**: Prerequisites, dependencies, environment setup
3. **Running Instructions**: How to start the server
4. **Testing Instructions**: How to verify functionality
5. **Acceptance Test Steps**: Manual steps user can perform

Before marking task complete:
- Verify application runs: `uv run python -c "from app import server"`
- Verify tests pass: `uv run pytest tests/ -v`
- Verify user can follow README to test
- Document all manual acceptance tests user should perform

## Application to Agent Definitions

### c3:python-developer Agent

**Current Behavior**: Writes complete tests immediately

**Updated Behavior**:
- **Iteration 1-MVP Projects**: Create test stubs as executable specifications
- Accept `pytest.fail("Not implemented: [behavior]")` as valid
- Focus on implementation correctness first
- Document test debt in summary

- **Stabilization Phase**: Fill in test stubs with assertions
- Add edge case tests
- Verify all error paths

- **Production Readiness**: Complete test coverage
- All assertions meaningful
- No `pass` statements or `assert True` placeholders

### c3:testing-engineer Agent

**Current Behavior**: Expects all tests to have proper assertions

**Updated Behavior**:
- **Iteration 1-MVP Projects**: Review test stubs as specifications
- Check that stubs describe expected behavior clearly
- Identify missing test scenarios, not incomplete assertions
- Mark test debt in review report

- **Stabilization Phase**: Verify test stubs have been filled in
- Check assertions are meaningful
- Identify edge cases missing coverage

- **Production Readiness**: Comprehensive review
- All assertions verify behavior
- No placeholders or stubs

### c3:functional-analyst Agent

**Current Behavior**: N/A (no test-related behavior)

**No Changes Required**: Functional analysis focuses on requirements, not implementation approach

### c3:project-manager Agent

**Current Behavior**: Enforces Phase 5 (Review Cycle) with blocking condition on incomplete tests

**Updated Behavior**:
- **Iteration 1-MVP Projects**: Accept test debt with documentation
- Non-blocking: Test stubs without assertions
- Blocking: No tests at all, or tests that would pass incorrectly
- Document test debt in summary report

- **Stabilization Phase**: Require filled-in tests
- Non-blocking: Minor edge cases missing
- Blocking: Core functionality untested

- **Production Readiness**: Strict test coverage
- Blocking: Any test debt
- All assertions must be meaningful

### c3:code-reviewer Agent

**Current Behavior**: Reviews code quality, mentions test placeholders as issues

**Updated Behavior**:
- **Iteration 1-MVP Projects**: Note test debt as "Technical Debt - Low Priority"
- Do not block approval
- Document in review summary

- **Stabilization Phase**: Flag unfilled test stubs as "Medium Priority"
- May block approval if core paths untested

- **Production Readiness**: Block on test debt
- Require all assertions meaningful

## Implementation in Agent Prompts

### Example for c3:python-developer

```markdown
## Testing Approach

Adapt testing depth based on project phase:

**MVP Phase (Iterations 1-2):**
- Create test stubs as executable specifications
- Use `pytest.fail("Not implemented: [expected behavior]")` format
- Focus on implementation correctness
- Document test debt in summary

**Stabilization Phase (Iterations 3-6):**
- Fill in test stubs with meaningful assertions
- Add edge case tests
- Verify error paths

**Production Readiness (Iterations 7+):**
- Comprehensive test coverage
- All tests have meaningful assertions
- No placeholders or stubs
```

### Example for c3:testing-engineer

```markdown
## Test Review Criteria

Adapt strictness based on project phase:

**MVP Phase (Iterations 1-2):**
- Test stubs acceptable as executable specifications
- Check behavior descriptions are clear
- Identify missing test scenarios
- Document test debt in review

**Stabilization Phase (Iterations 3-6):**
- Expect filled-in test stubs
- Check assertions verify behavior
- Flag edge cases missing coverage

**Production Readiness (Iterations 7+):**
- Comprehensive test coverage required
- All assertions meaningful
- No placeholders or stubs
```

## Decision Framework

When deciding test depth, consider:

1. **Project Phase**: Is this MVP, stabilization, or production?
2. **Iteration Number**: Lower iterations = more test debt acceptable
3. **Feature Stability**: Stable features need more test depth
4. **Deployment Target**: Production requires comprehensive tests

## Memory Trigger

When task includes "test stubs" or "incomplete tests" in review:
- Check project phase (TODO.md iteration number)
- Apply appropriate test depth standard
- Document test debt for future iterations
- Do not block MVP tasks on test depth

## Related Lessons

- **Agile Vertical Slices**: Complete features over complete layers
- **Technical Debt Management**: Document and track debt explicitly
- **Iterative Quality**: Quality increases as project matures

## References

- User clarification during I1-001 review: "In the agile project context the focus is on developing the end-to-end functionality. When features/requirements are close to final, the testing becomes more important. We first want to achieve speed, afterwards increase depth."