import json
import logging
import os
from time import sleep
from typing import Dict, List
from unittest import TestCase
from uuid import uuid4

import boto3
from botocore.client import BaseClient

"""
Make sure env variable AWS_SAM_STACK_NAME exists with the name of the stack we are going to test. 
"""


class TestStateMachine(TestCase):
    """
    This integration test will execute the step function and verify
    - "Record Transaction" is executed
    - the record has been inserted into the transaction record table.
    * The inserted record will be removed when test completed.
    """

    state_machine_arn: str
    lambda_function_validator: str
    lambda_function_purchase: str
    lambda_function_refund: str
    lambda_function_error: str
    transaction_table_purchase: str
    transaction_table_refund: str
    transaction_table_error: str

    client: BaseClient
    inserted_purchase_record_id = []
    inserted_refund_record_id = []
    inserted_error_record_id = [] 

    @classmethod
    def get_and_verify_stack_name(cls) -> str:
        stack_name = os.environ.get("AWS_SAM_STACK_NAME")
        if not stack_name:
            raise Exception(
                "Cannot find env var AWS_SAM_STACK_NAME. \n"
                "Please setup this environment variable with the stack name where we are running integration tests."
            )

        # Verify stack exists
        client = boto3.client("cloudformation")
        try:
            client.describe_stacks(StackName=stack_name)
        except Exception as e:
            raise Exception(
                f"Cannot find stack {stack_name}. \n" f'Please make sure stack with the name "{stack_name}" exists.'
            ) from e

        return stack_name

    @classmethod
    def setUpClass(cls) -> None:
        """
        Based on the provided env variable AWS_SAM_STACK_NAME,
        here we use cloudformation API to find out:
        - TransactionProcessorStateMachine's ARN
        - DDBPurchaseTable's table name
        """
        stack_name = TestStateMachine.get_and_verify_stack_name()

        client = boto3.client("cloudformation")
        response = client.list_stack_resources(StackName=stack_name)
        resources = response["StackResourceSummaries"]
        state_machine_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "TransactionProcessorStateMachine"
        ]
        transaction_table_purchase_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "PurchaseTable"
        ]
        transaction_table_refund_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "RefundTable"
        ]
        transaction_table_error_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "ErrorTable"
        ]
        lambda_function_purchase_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "PurchaseFunction"
        ]
        lambda_function_validator_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "ValidatorFunction"
        ]
        lambda_function_refund_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "RefundFunction"
        ]
        lambda_function_error_resources = [
            resource for resource in resources if resource["LogicalResourceId"] == "ErrorFunction"
        ]

        if not state_machine_resources:
            raise Exception("Cannot find TransactionProcessorStateMachine")
        if not transaction_table_purchase_resources:
            raise Exception("Cannot find DDBPurchaseTable")
        if not transaction_table_refund_resources:
            raise Exception("Cannot find DDBRefundTable")
        if not transaction_table_error_resources:
            raise Exception("Cannot find DDBErrorTable")
        if not lambda_function_error_resources:
            raise Exception("Cannot find ErrorFunction")
        if not lambda_function_purchase_resources:
            raise Exception("Cannot find PurchaseFunction")
        if not lambda_function_refund_resources:
            raise Exception("Cannot find RefundFunction")
        if not lambda_function_validator_resources:
            raise Exception("Cannot find ValidatorFunction")

        cls.state_machine_arn = state_machine_resources[0]["PhysicalResourceId"]
        cls.transaction_table_purchase = transaction_table_purchase_resources[0]["PhysicalResourceId"]
        cls.transaction_table_refund = transaction_table_refund_resources[0]["PhysicalResourceId"]
        cls.transaction_table_error = transaction_table_error_resources[0]["PhysicalResourceId"]
        cls.lambda_function_validator = lambda_function_validator_resources[0]["PhysicalResourceId"]
        cls.lambda_function_purchase = lambda_function_purchase_resources[0]["PhysicalResourceId"]
        cls.lambda_function_refund = lambda_function_refund_resources[0]["PhysicalResourceId"]
        cls.lambda_function_error = lambda_function_error_resources[0]["PhysicalResourceId"]

    def setUp(self) -> None:
        self.client = boto3.client("stepfunctions")

    def tearDown(self) -> None:
        """
        Delete the dynamodb table item that are created during the test
        """
        client = boto3.client("dynamodb")
        for id in self.inserted_purchase_record_id:
            client.delete_item(
                Key={
                    "TransactionId": {
                        "S": id,
                    },
                },
                TableName=self.transaction_table_purchase,
            )

        for id in self.inserted_refund_record_id:
            client.delete_item(
                Key={
                    "TransactionId": {
                        "S": id,
                    },
                },
                TableName=self.transaction_table_refund,
            )

        for id in self.inserted_error_record_id:
            client.delete_item(
                Key={
                    "TransactionId": {
                        "S": id,
                    },
                },
                TableName=self.transaction_table_error,
            )
      

    def _start_execute(self) -> str:
        """
        Start the state machine execution request and record the execution ARN
        """
        test_data = { "transactions": [
                {"Type": "PURCHASE"},
                {"Type": "REFUND"},
                {"Type": "PURCHASE"},
                {"Type": "REFUND"},
                {"Type": "PURCHASE"},
                {"Type": "FORERROR"},
                {"Type": "PURCHASE"},
                {"Type": "RAISEERROR"},
                {"Type": "PURCHASE"},
                {"Type": "REFUND"},
                {"Type": "REFUND"},
                {"Type": "PURCHASE"}
                ]
            }
        response = self.client.start_execution(
            stateMachineArn=self.state_machine_arn, name=f"integ-test-{uuid4()}", input=json.dumps(test_data)
        )
        return response["executionArn"]

    def _wait_execution(self, execution_arn: str):
        while True:
            response = self.client.describe_execution(executionArn=execution_arn)
            status = response["status"]
            if status == "SUCCEEDED":
                logging.info(f"Execution {execution_arn} completely successfully.")
                break
            elif status == "RUNNING":
                logging.info(f"Execution {execution_arn} is still running, waiting")
                sleep(3)
            else:
                self.fail(f"Execution {execution_arn} failed with status {status}")

    def _retrieve_transaction_table_input(self, execution_arn: str) -> Dict:
        """
        Make sure "Record Transaction" step was reached, and record the input of it.
        """
        response = self.client.get_execution_history(executionArn=execution_arn,maxResults=1000)
        events = response["events"]
        record_purchase_entered_events = [
            event
            for event in events
            if event["type"] == "TaskStateEntered" and event["stateEnteredEventDetails"]["name"] == "InsertPurchase"
        ]

        record_refund_entered_events = [
            event
            for event in events
            if event["type"] == "TaskStateEntered" and event["stateEnteredEventDetails"]["name"] == "InsertRefund"
        ]

        record_error_entered_events = [
            event
            for event in events
            if event["type"] == "TaskStateEntered" and event["stateEnteredEventDetails"]["name"] == "InsertError"
        ]
        
        self.assertTrue(
            record_purchase_entered_events,
            "Cannot find InsertPurchase TaskStateEntered event",
        )
        self.assertTrue(
            record_refund_entered_events,
            "Cannot find InsertPurchase TaskStateEntered event",
        )
        self.assertTrue(
            record_error_entered_events,
            "Cannot find InsertPurchase TaskStateEntered event",
        )
        purchase_table_input=[]
        refund_table_input=[]
        error_table_input=[]
        for transaction in record_purchase_entered_events:
            transaction_input = json.loads(transaction["stateEnteredEventDetails"]["input"])

            purchase_table_input.append(transaction_input)
            self.inserted_purchase_record_id.append(transaction_input["TransactionId"])  # save this ID for cleaning up

        for transaction in record_refund_entered_events:
            transaction_input = json.loads(transaction["stateEnteredEventDetails"]["input"])

            refund_table_input.append(transaction_input)
            self.inserted_refund_record_id.append(transaction_input["TransactionId"])  # save this ID for cleaning up

        for transaction in record_error_entered_events:
            transaction_input = json.loads(transaction["stateEnteredEventDetails"]["input"])

            error_table_input.append(transaction_input)
            self.inserted_error_record_id.append(transaction_input["TransactionId"])  # save this ID for cleaning up

        return purchase_table_input, refund_table_input, error_table_input

    def _verify_transaction_record_written(self, purchase_table_input: Dict, refund_table_input: Dict, error_table_input: Dict):
        """
        Use the input recorded in _retrieve_transaction_table_input() to
        verify whether the record has been written to dynamodb
        """
        client = boto3.client("dynamodb")
        for transaction_item in purchase_table_input:
            response = client.get_item(
                Key={
                    "TransactionId": {
                        "S": transaction_item["TransactionId"],
                    },
                },
                TableName=self.transaction_table_purchase,
            )
            self.assertTrue(
                "Item" in response,
                f'Cannot find transaction record with id {transaction_item["TransactionId"]}',
            )
            item = response["Item"]
            self.assertDictEqual(item["Message"], {"S": transaction_item["Message"]})
            self.assertDictEqual(item["Timestamp"], {"S": transaction_item["Timestamp"]})
            self.assertDictEqual(item["Type"], {"S": transaction_item["Type"]})

        for transaction_item in refund_table_input:
            response = client.get_item(
                Key={
                    "TransactionId": {
                        "S": transaction_item["TransactionId"],
                    },
                },
                TableName=self.transaction_table_refund,
            )
            self.assertTrue(
                "Item" in response,
                f'Cannot find transaction record with id {transaction_item["TransactionId"]}',
            )
            item = response["Item"]
            self.assertDictEqual(item["Message"], {"S": transaction_item["Message"]})
            self.assertDictEqual(item["Timestamp"], {"S": transaction_item["Timestamp"]})
            self.assertDictEqual(item["Type"], {"S": transaction_item["Type"]})

        for transaction_item in error_table_input:
            response = client.get_item(
                Key={
                    "TransactionId": {
                        "S": transaction_item["TransactionId"],
                    },
                },
                TableName=self.transaction_table_error,
            )
            self.assertTrue(
                "Item" in response,
                f'Cannot find transaction record with id {transaction_item["TransactionId"]}',
            )
            item = response["Item"]
            self.assertDictEqual(item["Message"], {"S": transaction_item["Message"]})
            self.assertDictEqual(item["Timestamp"], {"S": transaction_item["Timestamp"]})
            self.assertDictEqual(item["Type"], {"S": transaction_item["Type"]})

    def test_state_machine(self):
        execution_arn = self._start_execute()
        self._wait_execution(execution_arn)
        purchase_table_input, refund_table_input, error_table_input = self._retrieve_transaction_table_input(execution_arn)
        self._verify_transaction_record_written(purchase_table_input, refund_table_input, error_table_input)
