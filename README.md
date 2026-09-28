# LandLensAI + BuildingConstructor — Full Working Project

This repository is a complete educational prototype implementing the requested 20-feature workflow in a single Flask application.

## Included features

### LandLensAI (1–10)
1. Land image upload
2. Image quality check
3. Land classification baseline
4. Boundary/edge detection
5. Dimension entry using reference measurements
6. Area and perimeter calculation
7. Object-detection baseline
8. Buildable-area estimation
9. Plot visualization / processed image
10. Land analysis dashboard

### BuildingConstructor (11–20)
11. Building type selection
12. Floor selection
13. Requirements input
14. Conceptual 2D floor-plan generation
15. Material estimation
16. Construction cost estimation
17. Labour estimation
18. Construction timeline
19. AI-style/rule-based building recommendation
20. Final PDF construction report

## Run on Windows

Open the project folder in VS Code.

```powershell
py --version
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open:
http://127.0.0.1:5000

## If `python` does not work

Use:

```powershell
py app.py
```

## What is actually AI here?

The project intentionally uses working baseline computer-vision logic:
- OpenCV image quality metrics
- color/edge based land-type baseline
- contour/edge boundary detection
- baseline object indicators

A production ML classifier, segmentation model, object detector, cost model and LLM recommender require trained/validated data. The architecture is deliberately separated so those models can be added later without rebuilding the application.

## Important measurement limitation

A normal photograph cannot reliably give survey-grade length, width or area. The application therefore asks for reference dimensions and calculates:
Area = Length × Width
Perimeter = 2 × (Length + Width)
Buildable-area estimate = Area × (1 - open-space/setback percentage)

These are planning estimates only.

## Cost limitation

Material quantities and prices are illustrative estimation formulas. Update `services/building_service.py` with your local supplier rates and validated quantity-surveying assumptions.

## Project structure

- `app.py` — Flask entry point and routes
- `services/land_service.py` — image processing and land analysis
- `services/building_service.py` — floor plan, materials, cost, labour, timeline and recommendations
- `services/report_service.py` — PDF report
- `templates/` — web pages
- `static/` — CSS and JavaScript
- `uploads/`, `processed/`, `reports/` — generated files
- `landlensai.db` — created automatically on first run

## Presentation/demo flow

1. Upload a land image.
2. Show quality score and land-type baseline.
3. Show original vs edge/boundary map.
4. Enter length, width and setback percentage.
5. Explain area/buildable-area formula.
6. Choose building type, floors and rooms.
7. Generate conceptual floor plan.
8. Show materials and cost.
9. Show labour and timeline.
10. Download final PDF.

## Safety/professional note

This is a college project/prototype. It is not a legal land survey, structural design, architectural approval drawing, municipal approval, quantity-surveyor certificate, or professional construction quotation.
