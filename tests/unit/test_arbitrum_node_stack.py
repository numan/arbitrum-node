import aws_cdk as core
import aws_cdk.assertions as assertions

from arbitrum_node.arbitrum_node_stack import ArbitrumNodeStack

# example tests. To run these tests, uncomment this file along with the example
# resource in arbitrum_node/arbitrum_node_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = ArbitrumNodeStack(app, "arbitrum-node")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
