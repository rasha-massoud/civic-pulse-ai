# CivicPulse WhatsApp Multimodal AI Integration - Complete Testing Guide

## 📋 Overview

The full integration is now complete with the following flow:

```
WhatsApp Message (text/voice/image/location)
    ↓
FastAPI Webhook Handler
    ↓
Whisper Transcription (if voice)
    ↓
WhatsApp Conversation Service (collect info)
    ↓
OpenAI Multimodal Analysis (text + images + location)
    ↓
Session Updated with AI Results
    ↓
Confirmation Message Shown to User
    ↓
User Confirms → Report Saved to Database
```

---

## 🚀 Setup Steps

### 1. Apply Database Migration

Before running the backend, apply the new migration to add AI fields:

```bash
cd backend
alembic upgrade head
```

This creates the new database columns:
- `ai_summary` (text) - AI-generated summary
- `ai_confidence` (float) - Confidence score (0-1)
- `ai_image_findings` (JSON) - Detailed findings from image analysis
- `ai_uncertainties` (JSON) - List of uncertainties identified by AI

### 2. Start the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify the API is running: `GET http://localhost:8000/api/v1/health`

### 3. Verify Environment Variables

Check that these are set in your `.env`:

```env
OPENAI_API_KEY=sk-proj-... (your actual key)
OPENAI_MULTIMODAL_MODEL=gpt-4o-mini
OPENAI_MULTIMODAL_TIMEOUT_SECONDS=60.0
```

---

## 🧪 Testing Options

### Option A: Direct REST API (Easiest for Development)

Test the multimodal analysis endpoint directly without WhatsApp:

#### Request Example (Text Only)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/report \
  -H "Content-Type: application/json" \
  -d '{
    "citizen_text": "There is a pothole on Hamra Street blocking traffic",
    "location": {
      "text": "Hamra Street, Beirut"
    }
  }'
```

#### Request Example (With Location Coordinates)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/report \
  -H "Content-Type: application/json" \
  -d '{
    "citizen_text": "Big garbage pile at Martyrs Square, really needs cleanup",
    "location": {
      "text": "Martyrs Square",
      "latitude": 33.8950,
      "longitude": 35.4863
    }
  }'
```

#### Request Example (With Image URL)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/report \
  -H "Content-Type: application/json" \
  -d '{
    "citizen_text": "Streetlight broken on Achrafieh Road",
    "location": {
      "text": "Achrafieh Road, Beirut",
      "latitude": 33.8850,
      "longitude": 35.5100
    },
    "images": [
      {
        "url": "https://example.com/pothole.jpg"
      }
    ]
  }'
```

#### Response Example

```json
{
  "category": "street_light",
  "severity": "medium",
  "language": "English",
  "summary": "Broken streetlight on Achrafieh Road",
  "description": "Citizen reports a broken streetlight on Achrafieh Road that requires maintenance. Based on the photo and description, this is a standard municipal service request for lighting infrastructure repair.",
  "location_text": "Achrafieh Road, Beirut",
  "latitude": 33.8850,
  "longitude": 35.5100,
  "image_findings": [
    {
      "image_index": 1,
      "observation": "Broken glass visible at fixture base",
      "supports_report": true
    }
  ],
  "uncertainties": [],
  "confidence": 0.92
}
```

#### Using Postman

1. **Create Request**
   - Method: `POST`
   - URL: `http://localhost:8000/api/v1/analyze/report`
   - Headers: `Content-Type: application/json`

2. **Body (JSON)**
   ```json
   {
     "citizen_text": "Water leak on Rainbow Street, looks serious",
     "location": {
       "text": "Rainbow Street, Beirut"
     }
   }
   ```

3. **Send** → Get AI analysis response

---

### Option B: WhatsApp Integration Flow (End-to-End)

To test the complete WhatsApp flow:

1. **User sends WhatsApp message to your number**

2. **Backend receives webhook:**
   - Converts to text (transcribes if voice)
   - Collects information through multi-turn conversation:
     - Issue description
     - Location
     - Photo (optional)

3. **After collection → OpenAI Analysis runs:**
   - Analyzes all evidence together
   - Returns structured classification
   - Generates summary
   - Scores confidence

4. **Confirmation message shows to user:**
   ```
   Report summary:
   - Type: Pothole
   - AI Analysis: Large pothole on Hamra Street affecting traffic flow
   - Severity: High
   - Confidence: 94%
   - Description: There is a big hole in the street on Hamra Street
   - Location: Hamra Street, Beirut
   - Photos: 1
   
   Reply *yes* to submit or *no* to cancel
   ```

5. **User confirms ("yes"):**
   - Report saved to database with AI fields
   - Ticket reference returned (CIV-000123)

---

## 📊 Database Schema

The `reports` table now includes:

```sql
-- AI Analysis Fields (NEW)
ai_summary: TEXT              -- Short AI-generated summary
ai_confidence: FLOAT          -- AI confidence score (0-1)
ai_image_findings: JSON       -- Detailed image analysis
ai_uncertainties: JSON        -- List of uncertainties

-- Existing Fields
id: INT (Primary Key)
issue_id: INT (Foreign Key)
phone_number: VARCHAR(32)
transcribed_text: TEXT
category: VARCHAR(100)
severity: VARCHAR(50)
latitude: FLOAT
longitude: FLOAT
photo_url: VARCHAR(500)
language: VARCHAR(10)
created_at: DATETIME
```

---

## 🔍 Monitoring & Debugging

### Check Logs

The backend logs all multimodal analysis:

```
Multimodal analysis completed | phone=96170123456 category=pothole severity=high confidence=0.92 images=1
WhatsApp report persisted | issue_id=5 report_id=8 category=Pothole district=Hamra ai_confidence=0.92
```

### Verify Report in Database

```sql
SELECT 
  id,
  category,
  severity,
  ai_summary,
  ai_confidence,
  ai_image_findings,
  ai_uncertainties,
  created_at
FROM reports
ORDER BY created_at DESC
LIMIT 5;
```

### Check Session Storage (Redis)

WhatsApp session state is stored in Redis:
```
redis://localhost:6379/0
```

Key format: `whatsapp_session:{phone_number}`

---

## 🚨 Troubleshooting

### Error: "OPENAI_API_KEY is not configured"

**Fix:** Ensure `OPENAI_API_KEY` is set in `.env` and the backend was restarted after adding it.

### Error: "OpenAI returned no structured civic report"

**Issue:** OpenAI model didn't return valid structured output
**Fix:** 
- Check OpenAI API status
- Verify the model is `gpt-4o-mini` (not a typo)
- Increase `OPENAI_MULTIMODAL_TIMEOUT_SECONDS` to 120

### Error: "Multimodal analysis exhausted retries"

**Issue:** Transient API failure after 3 retries
**Fix:**
- Check internet connection
- Verify OpenAI API key is valid
- Check for rate limits on OpenAI account

### WhatsApp Message Not Processed

**Check:**
1. Is backend running? `curl http://localhost:8000/api/v1/health`
2. Are logs showing webhook receipt?
3. Is `META_WHATSAPP_WEBHOOK_VERIFY_TOKEN` correct?

---

## 📱 WhatsApp Flow Example (Step-by-Step)

### User Experience:

```
Citizen: "There is a big hole on Hamra Street"

Bot: "Thanks! Please share the exact location.
     You can send the address or your current location."

Citizen: "Hamra Street, Beirut"

Bot: "Can you send a photo of the issue? 
     Reply *skip* if you don't have one."

Citizen: [sends photo]

[🤖 OpenAI Analysis Runs in Background 🤖]

Bot: "Report summary:
     - Type: Pothole
     - AI Analysis: Large pothole on Hamra Street affecting traffic
     - Severity: High
     - Confidence: 94%
     - Description: There is a big hole in the street on Hamra Street
     - Location: Hamra Street, Beirut
     - Photos: 1
     
     Reply *yes* to submit or *no* to cancel."

Citizen: "yes"

Bot: "Your report has been submitted. Reference: CIV-000123. Thank you!"

Database: Report saved with ai_summary, ai_confidence, etc.
```

---

## 🎯 Next Steps

1. ✅ Database migration applied
2. ✅ Test REST endpoint with sample requests
3. ✅ Test WhatsApp flow with real message
4. ✅ Verify reports saved with AI fields in database
5. Optional: Add dashboard display of AI confidence scores
6. Optional: Implement AI-based deduplication of similar reports

---

## 📞 Support

If you encounter issues:

1. Check backend logs: `tail -f logs/app.log`
2. Verify OpenAI API key is valid
3. Test with direct REST API first (easier debugging)
4. Check database migration ran: `alembic current`
5. Review WhatsApp webhook verification in logs
