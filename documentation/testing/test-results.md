## Frontend Automated Tests

The frontend automated test suite was executed locally using Vitest.

**Command:**
```bash
cd frontend
npm run test
```

**Result:**
- 19 tests passed
- 0 tests failed
- 5 test files passed

Test coverage includes:
- API service behaviour
- Operation persistence and recovery
- Retry handling and duplicate submission prevention
- Authentication behaviour
- UI component behaviour

## Frontend Production Build

The frontend production build was verified successfully.

**Command:**
```bash
cd frontend
npm run build
```

**Result:**
- TypeScript compilation successful
- 2,188 modules transformed
- Vite production build completed successfully

## Combined Automated Test Results

| Test suite | Passed | Failed |
|---|---:|---:|
| Python / Backend | 52 | 0 |
| Frontend / Vitest | 19 | 0 |
| **Total** | **71** | **0** |

Note: These are results from two separate test suites, executed with their respective commands.

---

# Testing Results

## 1. Automated Test Suite

The full automated test suite was executed locally using Python and `pytest`.

**Command:**
```bash
python -m pytest -q
```

**Result:**
- 52 tests passed
- 0 tests failed
- Execution time: 0.14 seconds

The suite includes application tests and Terraform security configuration tests.

The application tests use in-memory AWS SDK mocks to test application logic without accessing real AWS resources.

Test coverage includes:
- Input validation and invalid requests
- Missing tickets
- Ticket creation, updates and soft deletion
- Idempotency and duplicate request handling
- Authorization and ownership checks
- SQS and SNS error handling
- Notification worker behaviour
- Audit and operation status handling
- Terraform security configuration checks

## 2. Manual End-to-End Tests

The application was deployed on AWS and tested through its user interface.

| Test | Result | Evidence |
|---|---|---|
| Create ticket | Successful | Ticket appeared in the ticket list |
| Read tickets | Successful | Tickets displayed in the application |
| Update ticket | Successful | Updated title displayed |
| Delete ticket | Successful | Ticket status changed to Deleted |

### Test Operation References

| Operation | Operation ID | Result |
|---|---|---|
| Create | `7d4dcbb8` | COMPLETED |
| Create | `6d5fdb12` | COMPLETED |
| Update | `37e9f8d1` | COMPLETED |
| Delete | `0e2cb981` | COMPLETED |

**Note:** The delete operation uses soft deletion. The ticket is marked as `Deleted` rather than physically removed from DynamoDB.

## 3. Testing Limitations

The automated application tests use mocked AWS clients. They verify application logic but do not replace tests against live AWS services.

Manual CRUD testing confirms the main ticket management flow, but does not establish load capacity or cover every AWS failure and recovery scenario.

Additional evidence for live AWS error scenarios and CloudWatch logging has not yet been fully documented.

## 4. Conclusion

The Python automated test suite completed with 52 passing tests and no failures. The frontend Vitest suite completed with 19 passing tests and no failures, for a combined total of 71 passing tests across both suites.

The main ticket management operations were also manually tested through the deployed AWS application.
