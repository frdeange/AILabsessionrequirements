# 📸 Screenshots Guide

This directory contains the screenshots used in the main README.md to showcase the Azure AI Provisioner application.

## Required Images

### 1. `deployment-form.png`
**Screenshot of:** The main deployment form page (`/`)
- **Should show:** 
  - Clean form interface with all fields visible
  - Service Principal Name and Secret Expiration Date fields
  - Model selection dropdown
  - Include Azure AI Search checkbox
  - Deploy Environment button
- **Recommended size:** 1200x800px or similar
- **Browser:** Use a clean browser window (no dev tools visible)

### 2. `deployment-progress.png`
**Screenshot of:** The live deployment page (`/deployment/{id}`)
- **Should show:**
  - Real-time Terraform logs streaming
  - Progress indicators
  - Live WebSocket connection showing Terraform execution
  - Resource creation messages
- **Recommended size:** 1200x800px or similar
- **Tip:** Capture during actual deployment for authentic logs

### 3. `deployment-results.png`
**Screenshot of:** The results page (`/results/{id}`)
- **Should show:**
  - "Required Info for Exercises" section with:
    - OpenAI Endpoint
    - Azure OpenAI Key
    - Service Principal App ID
    - Service Principal Secret
    - Azure AI Search credentials
  - "Additional Details" section
  - Copy buttons visible
  - Clean, organized layout
- **Recommended size:** 1200x800px or similar

## Tips for Great Screenshots

1. **Use a clean browser window** - No bookmarks bar, dev tools, or extensions visible
2. **Use the light theme** - Usually more readable in documentation
3. **Capture at 100% zoom** - Ensures text is crisp and readable
4. **Show realistic data** - Use meaningful resource names, not test values
5. **Crop appropriately** - Remove unnecessary browser chrome but keep enough context

## Image Optimization

- **Format:** PNG for screenshots (better quality for text)
- **Compression:** Use tools like TinyPNG to reduce file sizes
- **Alt text:** Already included in the README.md markdown

## Update Instructions

When the UI changes significantly:
1. Take new screenshots following the guidelines above
2. Replace the existing images with the same filenames
3. The README.md will automatically show the updated images