## **Aws Step Functions Example With Lambda And Dynamodb**

------------

### 1. State file embeded

Create new stack and deploy cloudformation template. 
#### Parameters:
ProjectName: Set your project name. 

### 2. State file uploaded to the S3 bucket.

Create new S3 bucket in the same region and upload state.json file. 
Create new CloudFormation stack and deploy template. 
#### Parameters:
ProjectName: Set your project name. 
StateFileLocation: S3 Bucket name where your state file resides. 
StateFileName: Your state file name with extension. 

![](images/State.JPG)


