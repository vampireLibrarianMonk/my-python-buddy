# User Guide: my-python-buddy

## Login Stage 1: User logs in

User will enter their credentials that were created from the Administrator.

![Login Page](documentation/supporting_images/01-02-login_page_local_https.png)

## Login Stage 2: User is required to change password

Upon logging in, the user is prompted to change their password for security purposes.

![Change Password](documentation/supporting_images/01-00-post-login-change-password.png)

## Login Stage 3: User changes password

The user will enter their old password, enter a new one then enter it again to confirm it.

![Password Changed](documentation/supporting_images/01-00-post-login-password-changed.png)

## Post Login Stage 1: User is prompted to submit a file

The user is directed to a submission screen where they can upload a Python file for analysis.

![Submit File](documentation/supporting_images/01-05-post-login-1.png)

## Post Login Stage 2: User has their input Python file submitted successfully

Upon upload, the system either confirms success...

![Submission Success](documentation/supporting_images/01-05-post-login-2.png)

...or states that the file is invalid.

![Submission Error](documentation/supporting_images/01-05-post-login-2-1.png)

## Post Login Stage 3: User is prompted to select from a list of analyzers

The user is presented the available analyzers, allowing the user to select the ones they want to run the code analysis. The user will then select `Analyze`.

![Analyzer Choice](documentation/supporting_images/01-05-post-login-3.png)

## Post Login Stage 4: Template Analyze Code Page (selected only Bandit for brevity)

User is redirected back to the `Upload` page with a filled out table with file metadata, options to view, re-analyze and view each analyzer status and results. User is asked to refresh the page once scans are completed until `Django Channels` are implemented

![Analysis Page](documentation/supporting_images/01-05-post-login-4_1.png)

![Analysis Page](documentation/supporting_images/01-05-post-login-4_2.png)

## Post Login Stage 5: Table expansion

Another file upload and selection of analyzers and `Analzye` will result in a table expansion of the next file.

![Analysis Page](documentation/supporting_images/01-05-post-login-4_2.png)

## Post Login Stage 6: Viewing an Analysis Page

Selecting `👁️` from the respective analyzer's results column will result in a redirect to the Analysis Results Page. Of which there are three sections:

- File and Analyzer Metadata
- Findings Table
- Source Code

Each selection of a findings row will result in the directing of the user to that specific code line and column color coded by that respective severity color.

![Analysis Page](documentation/supporting_images/01-07-post-login-5-analysis_1.png)
![Analysis Page](documentation/supporting_images/01-07-post-login-5-analysis_2.png)
![Analysis Page](documentation/supporting_images/01-07-post-login-5-analysis_3.png)

# Post Login Stage 7: Viewing of Uploaded File

Selecting `👁️` in the View File column will result in the new page consisting of the uploaded file in case the user wants to download it.

![Analysis Page](documentation/supporting_images/09-01-view-download.png)
