import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment
import sqlite3
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import csv
from matplotlib.backends.backend_pdf import PdfPages
import base64
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator



# Setup Headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,ml;q=0.7"
}

# Database Setup
def setup_database():
    connection = sqlite3.connect("unified_products_final.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ProductData (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ProductID INTEGER,
            ProductTitle TEXT,
            Seller TEXT,
            Price INTEGER,
            Date TEXT,
            Source TEXT,
            UNIQUE(ProductID, Seller, Date) ON CONFLICT REPLACE
        )
    """)

    connection.commit()
    return connection, cursor


# Amazon Scraping Function
def scrape_amazon(url):
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    product_title = soup.find("span", {"id": "productTitle"}).get_text(strip=True) if soup.find("span", {
        "id": "productTitle"}) else "N/A"
    seller = soup.find("a", {"id": "sellerProfileTriggerId"}).get_text(strip=True) if soup.find("a", {
        "id": "sellerProfileTriggerId"}) else "N/A"
    product_price = soup.find("span", {"class": "aok-offscreen"}).get_text(strip=True) if soup.find("span", {
        "class": "aok-offscreen"}) else "Sold Out"

    return {"ProductTitle": product_title, "Seller": seller, "Price": product_price}


def insert_data(cursor, data, source, product_id):
    date = datetime.now().strftime('%Y-%m-%d')

    # Check if an entry already exists for this product on today's date
    cursor.execute("""
        SELECT ID FROM ProductData
        WHERE ProductID = ? AND Seller = ? AND Date = ?
    """, (product_id, data["Seller"], date))

    existing_entry = cursor.fetchone()

    if existing_entry:
        # **Update the existing entry to store the latest price**
        cursor.execute("""
            UPDATE ProductData
            SET Price = ?, ProductTitle = ?
            WHERE ProductID = ? AND Seller = ? AND Date = ?
        """, (data["Price"], data["ProductTitle"], product_id, data["Seller"], date))

        print(f"✅ Updated price for {data['ProductTitle']} ({data['Seller']}) on {date}.")

    else:
        # **Insert new entry if no record exists for today**
        cursor.execute("""
            INSERT INTO ProductData (ProductID, ProductTitle, Seller, Price, Date, Source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, data["ProductTitle"], data["Seller"], data["Price"], date, source))

        print(f"✅ Inserted new entry for {data['ProductTitle']} ({data['Seller']}) on {date}.")

    cursor.connection.commit()

# Send First Email with Attachment
def send_first_email(recipient_emails):
    subject = "Initial Price Rank Report"
    body = "This is the first email with the price rank information and the attached report."
    send_email(subject, body, recipient_emails)

def connect_to_database():
    return sqlite3.connect("unified_products_final.db")  #used previous Database that was created by one of my team members

# Fetch Data from Database
def fetch_data():
    connection = connect_to_database()
    query = """
        SELECT Distinct ProductTitle as Product, FORMAT(Date, '%d-%m-%Y') as Date, Seller, Price
        FROM ProductData
        WHERE Price IS NOT NULL

    """
    data = pd.read_sql_query(query, connection)
    connection.close()
    data['Price'] = pd.to_numeric(data['Price'], errors='coerce')

    # Drop rows where Price is NaN (non-numeric values)
    data = data.dropna(subset=['Price'])
    return data

from dotenv import load_dotenv
import os

load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")

# Generate Report
def generate_report():
    data = fetch_data()
    valid_data = data[data['Product'] != 'N/A']

    if valid_data.empty:
        print("No valid data found for report generation.")
        return

    recipient_emails = EMAIL_SENDER

    pdf_filename = f"PriceReport_{datetime.now().date()}.pdf"
    print(f"Saving report as {pdf_filename}")

    rank_changes = []

    try:
        with PdfPages(pdf_filename) as pdf_pages:
            for product_name in valid_data["Product"].unique():
                processed_data, product_rank_changes = process_data(valid_data, product_name)

                if processed_data.empty:
                    print(f"No valid data available for product '{product_name}'. Skipping plot.")
                    continue

                create_plots(processed_data, product_name, pdf_pages)
                rank_changes.extend(product_rank_changes)

        print(f"Report saved successfully as {pdf_filename}")

        # Prepare email content
        if rank_changes:
            subject = "Product Rank Change Alert"
            email_body = "The following product(s) have experienced a rank change:\n\n"
            for change in rank_changes:
                email_body += (
                    f"Product: {change['Product']}\n"
                    f"Previous Rank: {change['Previous Rank']}\n"
                    f"Current Rank: {change['Current Rank']}\n\n"
                )
        else:
            subject = "Price Report - No Rank Changes"
            email_body = "No rank changes occurred for any products.\n\nSee the attached report for details."

        # Send the email with the PDF attachment
        send_email(subject, email_body, recipient_emails)

    except Exception as e:
        print(f"Error generating report: {e}")


# Process Data and Detect Rank Changes
def process_data(data, product_name, our_seller="Our Company"):
    data['Price'] = pd.to_numeric(data['Price'], errors='coerce')
    data.dropna(subset=['Price'], inplace=True)

    product_data = data[data["Product"] == product_name].copy()
    product_data["Date"] = pd.to_datetime(product_data["Date"])
    product_data.sort_values("Date", inplace=True)

    results = []
    previous_rank = None
    rank_changes = []

    for date, group in product_data.groupby("Date"):
        min_price = group["Price"].min()
        avg_price = group["Price"].mean()

        our_price = group[group["Seller"] == our_seller]["Price"].values[0] if our_seller in group[
            "Seller"].values else None

        # **Apply discount of €10 (or another amount)**
        if our_price is not None:
            our_price = max(our_price - 5, 0)  # Ensure price doesn't go negative

        rank = (
            group.sort_values(by="Price").reset_index()
            .query("Seller == @our_seller").index.min() + 1
            if our_seller in group["Seller"].values
            else None
        )

        # Detect rank changes
        if previous_rank is not None and rank != previous_rank:
            rank_changes.append({
                "Product": product_name,
                "Previous Rank": previous_rank,
                "Current Rank": rank
            })

        previous_rank = rank
        results.append({
            "Date": date,
            "Minimal Price": min_price,
            "Average Price": avg_price,
            "Our Price": our_price,
            "Rank": rank
        })

    result_df = pd.DataFrame(results)
    return result_df, rank_changes


# Create Plots
def create_plots(data, product_name, pdf_pages):
    """
    Plots 3 subplots for a given product:
      1) Minimal Price vs. Our Price
      2) Average Price vs. Our Price
      3) Our Price Rank
    Saves all subplots in the provided PdfPages object.
    """
    plt.figure(figsize=(12, 10))

    # Subplot 1: Min Price vs Our Price
    plt.subplot(3, 1, 1)
    plt.plot(data["Date"], data["Minimal Price"], label="Min Price", color="blue", marker="o")
    plt.plot(data["Date"], data["Our Price"], label="Our Price", color="orange", marker="x")
    plt.title(f"Minimal Price vs. Our Price for {product_name}")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    # Limit the number of x-axis ticks
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())  # Automatically adjust the ticks
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
    plt.xticks(rotation=45)

    # Subplot 2: Average Price vs Our Price
    plt.subplot(3, 1, 2)
    plt.plot(data["Date"], data["Average Price"], label="Average Price", color="green", marker="o")
    plt.plot(data["Date"], data["Our Price"], label="Our Price", color="orange", marker="x")
    plt.title(f"Average Price vs. Our Price for {product_name}")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    # Apply automatic x-axis tick formatting
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
    plt.xticks(rotation=45)

    # Subplot 3: Rank of Our Price
    plt.subplot(3, 1, 3)
    plt.plot(data["Date"], data["Rank"], label="Rank", color="purple", marker="o")
    plt.title(f"Rank of Our Price for {product_name}")
    plt.xlabel("Date")
    plt.ylabel("Rank")
    plt.gca().invert_yaxis()  # Lower rank is better
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    # Automatically format the x-axis to reduce the number of ticks
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
    plt.xticks(rotation=45)

    # Adjust layout to prevent overlap
    plt.tight_layout(pad=4.0)

    # Save all subplots to the PDF
    pdf_pages.savefig()
    plt.close()


load_dotenv()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# SendGrid Email Sending Function with Attachment
def send_email(subject, body, recipient_emails):

    sender_email = "reportsender24@gmail.com"  # Your SendGrid email address
    sendgrid_api_key = SENDGRID_API_KEY #  SendGrid API key

    message = Mail(
        from_email=sender_email,
        to_emails=recipient_emails,
        subject=subject,
        html_content=body
    )

    # Attach file if it exists in the project directory
    pdf_filename = f"PriceReport_{datetime.now().date()}.pdf"
    if os.path.exists(pdf_filename):
        with open(pdf_filename, 'rb') as file:
            encoded_file = base64.b64encode(file.read()).decode()
            attachment = Attachment(
                file_content=encoded_file,
                file_type='application/pdf',
                file_name=pdf_filename,
                disposition='attachment'
            )
            message.attachment = attachment
    else:
        print(f"File {pdf_filename} does not exist in the directory. No attachment will be sent.")

    try:
        # Initialize SendGrid client and send email
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        print(f"Email sent to {', '.join(recipient_emails)}.")
        print("Status Code:", response.status_code)
        print("Response Body:", response.body)
        print("Response Headers:", response.headers)
    except Exception as e:
        print(f"Error sending email: {str(e)}")

# Main Function
def main():
    connection, cursor = setup_database()

    # Amazon products scraping
    amazon_urls = pd.read_csv(
        "urls.csv")
    for idx, row in amazon_urls.iterrows():
        amazon_data = scrape_amazon(row['urls'])
        insert_data(cursor, amazon_data, "Amazon", idx + 1)

    # eBay and Otto fallback data
    product_data = pd.read_csv(
        "products.csv")
    for idx, row in product_data.iterrows():
        product_id = idx + 1 + len(amazon_urls)  # Ensure unique ProductID continuation
        # Insert Otto and eBay fallback data using G7 Price
        insert_data(cursor, {"ProductTitle": row["Product Name"], "Seller": "OTTO", "Price": row["G7 Price"]},
                    "Otto Fallback", product_id)
        insert_data(cursor, {"ProductTitle": row["Product Name"], "Seller": "eBay", "Price": row["G7 Price"]},
                    "eBay Fallback", product_id)
        # Insert 'Our Company' data using G7 Price
        insert_data(cursor, {"ProductTitle": row["Product Name"], "Seller": "Our Company", "Price": row["G7 Price"]},
                    "Our Company", product_id)

    cursor.close()
    connection.close()
    print("Data scraping and insertion completed.")

    # Setup the database and email configuration
    connection, cursor = setup_database()
    cursor.close()
    connection.close()
    print("Database setup completed.")

    # Generate the report
    generate_report()



if __name__ == "__main__":
    first_email_sent = True  # Initialize the first email flag
    main()



