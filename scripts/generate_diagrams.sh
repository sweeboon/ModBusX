#!/bin/bash
# Generate both PNG and SVG versions of all diagrams
plantuml -tpng docs/diagrams/*.puml -output docs/diagrams/generated
plantuml -tsvg docs/diagrams/*.puml -output docs/diagrams/generated