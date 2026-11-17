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

Selected live AWS error scenarios and CloudWatch evidence are documented in Section 4. Further end-to-end failure and recovery testing remains necessary.

## 4. Live AWS CloudWatch Evidence Review

A read-only review of deployed AWS resources and CloudWatch logs was performed on 17 November 2026 in the `eu-central-1` region.

### Monitoring Resources

The review identified:

- 7 CloudWatch alarms: 6 in `OK` state and 1 in `INSUFFICIENT_DATA` state.
- 6 CloudWatch Log Groups.
- 1 CloudWatch operations dashboard containing 3 widgets at the time of the initial review.

**Monitoring improvement deployed on 17 November 2026:** The operations dashboard was updated from 3 to 5 widgets. The existing Lambda activity, SQS queues, and DynamoDB capacity widgets were retained. Two widgets were added:

- **Notification Worker:** Lambda invocations, errors, and average duration.
- **API Gateway Errors:** HTTP 4XX and 5XX error metrics for stage `v1`.

The update was deployed using a dedicated, limited-permission IAM user through the AWS CLI, without deploying Lambda or API Gateway changes. A subsequent AWS `GetDashboard` check confirmed that all 5 widgets were present.

The DLQ alarm was in `INSUFFICIENT_DATA` with no recent metric datapoints available during the review. An `OK` alarm state does not necessarily prove the absence of errors when missing data is configured as `notBreaching`.

Five application-related Log Groups had a 7-day retention period. The additional `/aws/apigateway/welcome` Log Group had no explicit retention period configured.

### API Gateway Error Evidence

CloudWatch access logs from 15 November 2026 contained the following events in the retrieved samples:

- 6 HTTP 403 responses for `GET /tickets`.
- 3 HTTP 404 responses for `GET /requests/{operation_id}`.
- 8 HTTP 500 responses for `GET /tickets`.
- 1 HTTP 500 response for `POST /tickets`.

These observations are based on filtered log samples and are not exhaustive request counts.

### Lambda Error Investigation

**Read Lambda:** CloudWatch logs showed an `AttributeError` caused by calling `.get()` on a null `pathParameters` value. Inspection of the currently deployed Lambda package confirmed that the code now uses `event.get("pathParameters") or {}`.

**Idempotency Lambda:** The HTTP 500 response for `POST /tickets` at 13:01:55 UTC on 15 November 2026 corresponded to an `AttributeError` recorded by the Idempotency Lambda. The currently deployed package also handles null `pathParameters` safely. However, the precise cause of this historical error remains unconfirmed because the available log entry did not contain a traceback.

Both Lambda functions were updated after their respective historical errors.

### Review Limitations

This review inspected deployed configurations, code packages, and selected CloudWatch logs. It did not modify AWS resources, execute new end-to-end API tests, verify notification delivery, or establish that all historical errors have been resolved.

## 5. Conclusion

The Python automated test suite completed with 52 passing tests and no failures. The frontend Vitest suite completed with 19 passing tests and no failures, for a combined total of 71 passing tests across both suites.

The main ticket management operations were also manually tested through the deployed AWS application.
