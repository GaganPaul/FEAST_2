# FEAST - Community Kitchen Network

FEAST is a technology-driven food redistribution system that connects donors, community kitchens, and food seekers via a mobile app and SMS platform.

## Project Overview

The FEAST platform aims to:
- Identify & distribute surplus food efficiently
- Enable real-time coordination between stakeholders
- Ensure inclusivity with both online and offline accessibility
- Optimize logistics for food pickup and delivery
- Promote food safety and responsible donations

## Features

- **Multi-user Roles**: Support for donors, volunteers, community kitchens, and food seekers
- **Real-time Location Tracking**: Track volunteers for efficient food pickup and delivery
- **Food Donation Management**: Register and track food donations
- **Food Request System**: Allow food seekers to request meals or grocery packages
- **Community Kitchen Dashboard**: Manage food inventory and meal planning
- **Interactive Maps**: Locate nearby resources and get directions
- **SMS Integration**: Ensure accessibility for users without smartphones

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: MongoDB
- **Frontend**: HTML, CSS, JavaScript
- **Maps Integration**: Google Maps API
- **SMS Integration**: Ready for integration with SMS gateways

## Installation

1. Clone the repository:
```
git clone https://github.com/yourusername/FEAST.git
cd FEAST
```

2. Create a virtual environment and activate it:
```
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On macOS/Linux
```

3. Install the required packages:
```
pip install -r requirements.txt
```

4. Set up MongoDB:
   - Install MongoDB if not already installed
   - Create a database named `feast_db`

5. Configure environment variables:
   - Create a `.env` file in the project root
   - Add the following variables:
     ```
     FLASK_APP=app.py
     FLASK_ENV=development
     MONGO_URI=mongodb://localhost:27017/feast_db
     GOOGLE_MAPS_API_KEY=your_google_maps_api_key
     ```

6. Run the application:
```
flask run
```

7. Open your browser and navigate to `http://localhost:5000`

## Project Structure

```
FEAST/
├── app.py                # Main application file
├── static/               # Static assets
│   ├── css/              # CSS stylesheets
│   ├── js/               # JavaScript files
│   └── images/           # Image assets
├── templates/            # HTML templates
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── login.html        # Login page
│   ├── register.html     # Registration page
│   ├── volunteer.html    # Volunteer dashboard
│   ├── kitchen.html      # Community kitchen dashboard
│   ├── seeker.html       # Food seeker dashboard
│   ├── donor.html        # Donor dashboard
│   ├── donate.html       # Food donation form
│   └── request_food.html # Food request form
└── requirements.txt      # Python dependencies
```

## Getting a Google Maps API Key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Maps JavaScript API, Directions API, and Places API
4. Create an API key and restrict it to your domains
5. Replace `YOUR_GOOGLE_MAPS_API_KEY` in the HTML templates with your actual API key

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- This project was created to address food insecurity and reduce food waste in communities
- Special thanks to all contributors and stakeholders who support this initiative
