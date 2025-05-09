# Price Collection System
This is a Price Collection System, which collects certain product prices from multiple e-commerce platforms, stores them in an SQLite database, generates a daily PDF report, and sends the report via email using the SendGrid API. The system is deployed on Google Cloud Platform (GCP) Virtual Machine (VM) instances and is scheduled to execute automatically using cron jobs.


## Features

* Web scraping of product prices from Amazon, Otto, and eBay.
* Storage of collected data in an SQLite database.
* Automated daily report generation in PDF format.
* Email notification using the SendGrid API.
* Automated execution using cron jobs in GCP.

## Project Structure

project-directory/

* main.py            # Main script for scraping, database handling, and email reporting
* requirements.txt   # Required Python libraries
* app.yaml           # GCP deployment configuration
* venv/              # Virtual environment
* urls.csv           # List of product URLs to scrape
* products.csv       # List of product URLs to scrape
* README.md          # Documentation

## Technologies Used
* Python 3
* SQLite (Database)
* BeautifulSoup (Web Scraping)
* Matplotlib (Data Visualization)
* SendGrid API (Email Notification)
* Google Cloud Platform (GCP)
* Cron Jobs (Task Scheduling)
* dotenv (loads environment variables from a .env where Sendgrid API key is stored)

# Installation and Setup

## **Setting Up the Virtual Environment**

`python -m venv venv`
`source venv/bin/activate`
`pip install -r requirements.txt`

## **Database Setup**
Run the script to create the SQLite database and tables:

`python main.py`

## **Configuring SendGrid API**

1. Creating a SendGrid API Key from SendGrid.

2. Setting it as an environment variable:

`export SENDGRID_API_KEY='your_api_key'`

## **Google Cloud Platform Integration**

This project runs on Google Cloud Platform and uses:

- **Compute Engine** for server-side processing
- **Cloud Storage** for saving results
- **IAM & APIs** for managing secure access and keys

All code was run via terminal using SSH on a GCP VM (Ubuntu 22.04).  
Due to the large volume of scripts and security-sensitive files, only key portions are included here.

You can replicate this setup by:
1. Creating a Compute Engine instance
2. Installing dependencies listed in `requirements.txt`
3. Running `main.py` with appropriate credentials


## **Running the Project locally**

_Manual Execution_

To execute the script manually:
`python main.py`

_Automated Execution via Cron Job_

To schedule the script to run daily at midnight:

`crontab -e`

Add the following line:

`0 0 * * * cd /path/to/the/project && /path/to/the/project/venv/bin/python3 main.py >> cron.log 2>&1`



# Troubleshooting

## **Cron Job Not Running**

Check the logs:

`grep CRON /var/log/syslog`
`cat /home/your-username/project-directory/cron.log`

## **Email Not Being Sent**

Manually test SendGrid:

`python -c "from sendgrid import SendGridAPIClient; sg = SendGridAPIClient('your_api_key'); print(sg.client.mail.send)"`


Expected output: <Response [202]>



