@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "PLANTUML_VERSION=1.2023.13"
set "DIAGRAMS_SOURCE=docs\diagrams"
set "DIAGRAMS_OUTPUT=%DIAGRAMS_SOURCE%\generated"
set "PLANTUML_JAR=plantuml.jar"
set "VALIDATE=false"

:: Parse arguments
:parse_args
if "%~1"=="" goto :args_parsed
if /i "%~1"=="--validate" set "VALIDATE=true" & shift & goto :parse_args
if /i "%~1"=="-v" set "VALIDATE=true" & shift & goto :parse_args
if /i "%~1"=="-h" goto :usage
if /i "%~1"=="--help" goto :usage
shift
goto :parse_args

:args_parsed

echo.
echo ModBusX PlantUML Diagram Generator (Windows)
echo ============================================

:: Check Java
where java >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Java is not installed or not in PATH.
    echo Please install Java 11 or later to run PlantUML.
    exit /b 1
)

echo Checking Java version...
java -version 2>nul | findstr /i "version"

:: Check/Download PlantUML
if not exist "%PLANTUML_JAR%" (
    set "URL=https://github.com/plantuml/plantuml/releases/download/v%PLANTUML_VERSION%/plantuml-%PLANTUML_VERSION%.jar"
    echo PlantUML JAR not found. Downloading v%PLANTUML_VERSION%...
    
    :: Try curl first (available in modern Windows)
    where curl >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        curl -L "!URL!" -o "%PLANTUML_JAR%"
    ) else (
        :: Fallback to PowerShell
        powershell -Command "Invoke-WebRequest -Uri '!URL!' -OutFile '%PLANTUML_JAR%'"
    )
    
    if not exist "%PLANTUML_JAR%" (
        echo ERROR: Failed to download PlantUML.
        exit /b 1
    )
)

:: Verify PlantUML
echo Verifying PlantUML...
java -Djava.awt.headless=true -jar "%PLANTUML_JAR%" -version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PlantUML verification failed.
    exit /b 1
)

if not exist "%DIAGRAMS_OUTPUT%" mkdir "%DIAGRAMS_OUTPUT%"

if not exist "%DIAGRAMS_SOURCE%" (
    echo ERROR: Source directory not found: %DIAGRAMS_SOURCE%
    exit /b 1
)

echo Found PlantUML files in %DIAGRAMS_SOURCE%...

pushd "%DIAGRAMS_SOURCE%"

echo Generating SVG diagrams...
:: Check for config file
set "CONFIG_ARG="
if exist "plantuml.config" (
    set "CONFIG_ARG=-config plantuml.config"
)

:: Run generation, output to the 'generated' subdirectory
:: Note: We use absolute path to JAR because we pushed into docs/diagrams
java -Djava.awt.headless=true -jar "%ROOT_DIR%%PLANTUML_JAR%" -tsvg -o "generated" %CONFIG_ARG% *.puml

popd

echo.
echo Generated files:
dir /b "%DIAGRAMS_OUTPUT%\*.svg" 2>nul | find /c /v ""

if "%VALIDATE%"=="true" (
    echo.
    echo Validating PlantUML syntax...
    set "VALIDATION_FAILED=false"
    
    for %%f in ("%DIAGRAMS_SOURCE%\*.puml") do (
        set "FILENAME=%%~nxf"
        <nul set /p="  Checking !FILENAME!... "
        java -Djava.awt.headless=true -jar "%PLANTUML_JAR%" -checkonly "%%f" >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            echo OK
        ) else (
            echo ERROR
            set "VALIDATION_FAILED=true"
        )
    )
    
    if "!VALIDATION_FAILED!"=="true" (
        echo ERROR: Some files have syntax errors.
        exit /b 1
    )
)

echo.
echo Diagram generation complete.
echo Output directory: %DIAGRAMS_OUTPUT%
exit /b 0

:usage
echo Usage: %~nx0 [--validate^|-v]
exit /b 0
