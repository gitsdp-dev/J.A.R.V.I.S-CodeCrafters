# J.A.R.V.I.S - MAKING MULTI-TASKING AND RESEARCHING EASIER
Presenting you J.A.R.V.I.S, a Python-coded ai assistant that can increase your knowledge and workflow easier. J.A.R.V.I.S is evolving into a more flexible and robust system. It bridges the gap between the operating system and human communication. Through natural dialogue, J.A.R.V.I.S analyzes your screen, processes uploaded documents, and executes complex workflows with a brand-new, adaptive interface that can give you Iron-Man Like capabilities on your computer.
#
It is not just a simple ChatGPT or any chatbot, it is the gamechanger for you that helps you to keep up your own flow in this extremely busy, digital, evolving world. 
#
## Capabilities

### Core Features
| Feature | Description |
|---|---|
|  Real-time Voice | Low latency conversation in any language |
|  System Control | Launch apps, manage files, execute terminal commands |
|  Autonomous Tasks | High-level planning for complex, multi-step goals |
|  Visual Awareness | Real-time screen processing and webcam vision |
|  Persistent Memory | Deeply remembers your projects, preferences, and personal context |
|  Hybrid Input | Seamlessly switch between keyboard typing and voice commands |

---
#
## Steps to Install and activate it in your PC
1. Download Python 3.14 or above (if released) and VS Code or any IDE of your choice (I will prefer VS code for its interactive user-friendly environment and stability and versatility if you construct virtual environments(Happened in my case for initialising J.A.R.V.I.S 😅)
   ### Links for Downloading these stuff:
   a. Python Package: https://www.python.org/downloads/ 

   b. VS Code Standard (Most Popular and stable): https://code.visualstudio.com/download 

      .........or......... 

      VS Code Insiders (For getting early access to new updates and features): https://code.visualstudio.com/insiders
3. Set Up VS Code (very easy, the software will guide you)
4. Download ZIP file of my repository files:

   <img width="1904" height="966" alt="image" src="https://github.com/user-attachments/assets/08d00400-f64a-491e-90ec-c8bb48beaa99" />




   ........Then........

   



   <img width="949" height="112" alt="image" src="https://github.com/user-attachments/assets/f28377a0-2998-4d1e-8717-08f69462d869" />

 5. Extract the ZIP file in your desired location
 6. Open the extracte folder in VS Code.
 7. Install the Python Extensions and dependencies recommended by VS Code. It will show those recommendations in the bottom right corner of the screen, in the notification bell icon. (It may also tell you to set up a virtual environment for the setup, do that then). It will take a minute or few minutes depening on your network speed. 
 8. Click on VS Code terminal and start executing this commaand for your JARVIS folder:
    ```
    pip install -r requirements.txt
    playwright install
    ```
    
 9.  Once done, run the code in the terminal of VS Code: (this command is required if you have to install the virtual environment from VS Code (this can automatically be run by vs code too))
   ```
   (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& YOUR_JARVIS_FOLDER_DIRECTORY\.venv\Scripts\Activate.ps1)
   ```
 10. After doing all these, run this command to initialise your own J.A.R.V.I.S:
     ```
     python main.py
     ```
 11. The J.A.R.V.I.S opens in your computer for the first time. It will ask you for a Gemini API key.
 12. For the API key, head to https://ai.google.dev/gemini-api/docs/api-key and click on Get API Key and create a key (make sure to copy and enter the key before the window for API key copying closes as you cannot copy the key again). Don't worry, the API key is completely free forever. 
 13. Enter the copied API key and select the operating system you are using it on, and then, click on "Initialize". It will remember your API key forever.
#
## Requirements

| Requirement | Details |
|---|---|
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11 or 3.12 or above |
| **Microphone and Speaker** | Required for voice interaction with JARVIS |
| **API Key** | Free Gemini API key |

---
#
## If you want to run it again and again fast
You need not open VS code again and again for initialising the J.A.R.V.I.S startup. What you have to do is:

Step 1: Open Windows Powershell 

Step 2: Run these commands in Powershell one after the other: (For no Virtual Environment setup)
   ```
   cd YOUR_JARVIS_FOLDER_DIRECTORY
   python main.py
   ```
** If you required to make a Virtual Environment in VS Code, run these commands one after the other:
   ```
   cd YOUR_JARVIS_FOLDER_DIRECTORY
   (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& YOUR_JARVIS_FOLDER_DIRECTORY\.venv\Scripts\Activate.ps1)
   python main.py
   ```

<strong> ** IMPORTANT NOTE: </strong> YOUR_JARVIS_FOLDER_DIRECTORY can be for example: C:\JARVIS or F:\J.A.R.V.I.S or according to your saved folder PATH. 
    
 

   
   
