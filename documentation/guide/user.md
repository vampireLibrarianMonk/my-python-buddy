# User Guide: my-python-buddy

## Post Login Stage 1: User logs in

User will enter their credentials that were created from the Administrator.

![Login Page](documentation/supporting_images/01-02-login_page_local_https.png)

## Post Login Stage 2: User is required to change password

Upon logging in, the user is prompted to change their password for security purposes.

![Change Password](documentation/supporting_images/01-00-post-login-change-password.png)

## Post Login Stage 3: User changes password

The user will enter their old password, enter a new one then enter it again to confirm it.

![Password Changed](documentation/supporting_images/01-00-post-login-password-changed.png)

## Post Login Stage 4: User is prompted to submit a file

The user is directed to a submission screen where they can upload a Python file for analysis.

![Submit File](documentation/supporting_images/01-05-post-login-1.png)

## Post Login Stage 5: User has their input Python file submitted successfully

Upon upload, the system either confirms success...

![Submission Success](documentation/supporting_images/01-05-post-login-2.png)

...or states that the file is invalid.

![Submission Error](documentation/supporting_images/01-05-post-login-2-1.png)

## Post Login Stage 6: User is prompted to select from a list of analyzers

The user is presented the available analyzers, allowing the user to select the ones they want to run the code analysis. The user will then select `Run analysis`.

![Analyzer Choice](documentation/supporting_images/01-05-post-login-3.png)

## Post Login Stage 7: Template Analyze Code Page (selected only Bandit for brevity)

The use is presented with the Analysis (currently templated) page that shows side-by-side the code with numbered lines and the part that will display the security findings and LLM recommendations.

![Analysis Page](documentation/supporting_images/01-05-post-login-4.png)

## Post Login Stage 8: Revisit submission page where previous submission is visible

Upon selection of the `Upload` in the upper right hand menu the user is returned to the submission page that has a table displaying the last submission as a row with future functionality being that analysis can be re-run or even deleted..

![Upload Screen Table](documentation/supporting_images/01-05-post-login-5.png)
