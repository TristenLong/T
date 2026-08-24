Feature: Jester AI Core
  As a scientist
  I want a full self learning ai and problem solver
  So that I can detect anomalies and test science hypotheses

  Background:
    Given the jester ai is active

  # ==========================================
  # API SCENARIOS
  # ==========================================
  Scenario Outline: Submit data for anomaly detection
    When the client sends a POST request to "/api/anomaly-detect" with <dataset_type> data
    Then the response status should be <status_code>
    And the response should contain "<expected_output>"

    Examples:
      | dataset_type | status_code | expected_output          |
      | valid        | 200         | anomalies_found          |
      | invalid      | 400         | Invalid dataset format   |

  # ==========================================
  # UI SCENARIOS
  # ==========================================
  Scenario: Run self learning training successfully
    Given the user is on the jester dashboard
    When the user clicks the "Start Self Learning" button
    Then the user should see a "Training initiated" notification
    And the loading spinner should be visible

  Scenario: Prevent duplicate training sessions
    Given the user is on the jester dashboard
    And the system is already in "Training" state
    When the user clicks the "Start Self Learning" button
    Then the "Start Self Learning" button should be disabled
    And the user should see an error message "Training already in progress"
