````markdown
# 🔍 Missing Person Finder

A Streamlit-based web application to help register, locate, and manage missing person cases using facial similarity, geolocation mapping, and secure user access.  
Built with 💙 for humanitarian aid and rescue efforts.

---

## 🚀 Features

- **Secure Login & Registration** with access code protection
- **Register Missing Person**:
  - Upload reference image
  - Store demographic details, contact info, Aadhaar (optional)
  - Automatic geocoding of last-seen location
- **Face Similarity Search**:
  - Upload photo to find matches using face embeddings + cosine similarity
  - Adjustable **strictness slider** for precise or broad matches
- **Interactive Map Previews** using Folium for:
  - Last seen locations
  - Overview of all matched cases
- **My Submitted Cases** tab for user-specific tracking
- **Mark as Found**:
  - Seamlessly archive resolved cases
  - View found persons with minimal info display

---

## 🧰 Tech Stack

| Tech              | Usage                                |
|-------------------|---------------------------------------|
| **Python**        | Core language                        |
| **Streamlit**     | Frontend + UI framework              |
| **SQLite**        | Lightweight local DB                 |
| **NumPy**         | Face embedding vector handling       |
| **Pandas**        | Tabular data manipulation            |
| **Folium**        | Interactive map rendering            |
| **Geopy**         | Geocoding from user input            |
| **PIL**           | Image display and I/O                |

---

## 🛠️ Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/missing-person-finder.git
   cd missing-person-finder
````

2. **Install required packages**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**:

   ```bash
   streamlit run app.py
   ```

4. 📂 A `photos/` folder will be auto-created to store uploaded images.

---

## 📁 Folder Structure

```
├── app.py               # Main Streamlit app
├── db.py                # Database schema & helper functions
├── face_utils.py        # Facial recognition utils (embedding, cosine)
├── photos/              # Uploaded photos saved here
├── requirements.txt     # Dependencies
└── README.md
```

---

## 🔒 Access Control

* Registration requires an **Access Code** (`admin123`, `rescue007`, or `verified2025`)
* Users can:

  * Submit missing person records
  * Search and manage only their own cases
* All password storage uses basic SHA-256 (demo-only — use salted hashing in production)

---

## ✅ Demo Highlights

* Map is shown **only if coordinates are available**
* **Face matching strictness slider**: Higher = stricter
* Cases marked as "Found" are moved to a separate table (`found_persons`)

---

## 📌 TODO / Improvements

* Use cloud database for multi-user access
* Integrate real face recognition (e.g., FaceNet or OpenCV)
* Add image deduplication / detection of duplicates
* SMS/email alerts on match
* Admin dashboard for oversight

---

## 🤝 Contribution

PRs are welcome! Please open an issue before submitting large changes.

---

## 📄 License

This project is for educational/demonstration purposes and is provided under the MIT License.

---

## 🙏 Credits

* Developed by \ Alok Kushwaha
* Powered by open-source tools and Streamlit

```
