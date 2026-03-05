# AutoPASS Toll Management System

A full-stack web application that simulates a modern toll road management system (bompengeselskap). The platform provides secure user registration, vehicle management, and dynamic toll pricing calculations based on real-world variables like rush-hour traffic and vehicle fuel types.

## 🚀 Features (In Progress)

* **Secure Authentication:** User registration and login with encrypted password hashing (`bcrypt`).
* **Dynamic Pricing Engine:** Advanced database logic calculates toll fees dynamically, applying discounts for EVs/Hybrids and surcharges during peak traffic hours (07:00-08:30, 15:30-17:00).
* **Passage Tracking:** Records vehicle passages at various toll stations and links them to registered users.
* **Responsive UI:** Clean, responsive web interface built with Bootstrap and Jinja2 templates.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI
* **Database:** SQLite3 (Asynchronous operations via `aiosqlite`)
* **Frontend:** HTML5, CSS3, Bootstrap, Jinja2
* **Security:** `werkzeug.security` (Password hashing)

## 🗄️ Database Architecture

A core component of this project is its robust SQLite architecture, which offloads complex business logic to the database layer:
* **Views (`all_passages`):** Handles complex conditional math for base prices, time multipliers, and fuel discounts on the fly.
* **Triggers:** Automates the registration of unknown vehicles passing through toll stations.
* **Constraints & Validation:** Ensures data integrity for phone numbers, fuel types, and foreign key relationships.

## ⚙️ Local Setup & Installation

1. Clone the repository:
```bash
git clone https://github.com/SHS34S0/autopass-toll-system.git
   cd autopass-toll-system 
```