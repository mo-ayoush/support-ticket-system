# Testing Results

## 1. Automated Application Tests

The application tests were executed locally using Python and `pytest`.

**Command:**
```bash
python -m pytest -q tests/test_common.py tests/test_lambda_handlers.py
```

**Result:**
- 43 tests passed
- 0 tests failed
- Execution time: 0.11 seconds

These tests use in-memory AWS SDK mocks to test application logic without accessing real AWS resources.

Test coverage includes:
- Input validation and invalid requests
- Missing tickets
- Ticket creation, updates and soft deletion
- Idempotency and duplicate request handling
- Authorization and ownership checks
- SQS and SNS error handling
- Notification worker behaviour
- Audit and operation status handling

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

The automated tests use mocked AWS clients. They verify application logic but do not replace tests against live AWS services.

Additional evidence for live AWS error scenarios and CloudWatch logging will be documented separately.

## 4. Conclusion

The selected automated application test suites completed successfully, with 43 passing tests and no failures.

The main ticket management operations were also manually tested through the deployed AWS application.
