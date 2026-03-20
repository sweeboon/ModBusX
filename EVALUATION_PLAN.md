# ModBusX Evaluation Plan (DECIDE Framework)

This evaluation framework follows the **DECIDE** model as outlined in the project documentation.

## 1. Determine the aims and goals
**What are the high level objectives of the evaluation?**
To compare the usability and efficiency of **ModBusX** against a standard, widely-used **Modbus Slave Simulator** (Competitor).

**Who wants it and why?**
The development team needs to validate that ModBusX's modern UI features (Search Bar, Quick Address Toggles, Side-by-side Formatting) provide a measurable productivity advantage over traditional tools.

**Goals:**
1.  **Assess extent of system's functionality:** Verify that ModBusX features like the Search Bar and Address Mode toggle work as intended.
2.  **Assess effect of interface on user:** Measure the reduction in time and clicks required to navigate large register maps and interpret data.
3.  **Identify specific problems with system:** Pinpoint any friction points in the new UI controls.

## 2. Explore the questions
**Primary Question:**
Is ModBusX significantly faster than standard software for navigating and interpreting Modbus register data?

**Sub-questions:**
1.  **Navigation Speed:** How much time is saved locating a specific register using the Search Bar vs. scrolling/paging?
2.  **Cognitive Load:** Is switching between PLC (Base 1) and Protocol (Base 0) addressing less mentally demanding in ModBusX?
3.  **Data Interpretation:** Is reading multi-format data (Hex/Binary/Signed) faster with the side-by-side inspector?

## 3. Choose the evaluation approach/method
**Paradigm:** Empirical Evaluation (Lab Study / A/B Testing).
**Method:** "Think Aloud" Protocol combined with Automatic Logging (for ModBusX) and Manual Timing (for Competitor).

-   **Empirical Evaluation:**
    -   **Design:** Within-Subjects. Each user performs the same set of tasks on **both** tools.
    -   **Counterbalancing:** Half the users start with ModBusX, half with the Competitor tool.

-   **Think Aloud:**
    -   Users explain their navigation strategy (e.g., "I'm scrolling down to find 40100...").

## 4. Identify practical issues
-   **Select Users:** Target 5-10 participants familiar with Modbus concepts.
-   **Select Equipment:**
    -   **Tool A:** ModBusX (Instrumented).
    -   **Tool B:** Standard Modbus Slave (e.g., Modbus Slave by Witte or similar).
    -   **Dataset:** Both tools pre-loaded with a configuration of 500 Holding Registers.
-   **Metrics:**
    -   **ModBusX:** Logs from `usability_logger` (timestamps for Search, Address Toggle).
    -   **Competitor:** Stopwatch timing by observer.

## 5. Decide how to deal with ethical issues
-   **Informed Consent:** Users agree to screen recording and data collection.
-   **Anonymity:** No names in logs.
-   **Rights:** User can stop the test if frustrated.

## 6. Evaluate, analyze, interpret and present data
**Data Collection:**
1.  **Task 1 (Search):** Time to locate Register 40450 and change its value.
2.  **Task 2 (Addressing):** Time to switch view from Base 1 to Base 0 and identify the Protocol Address of Register 40010.
3.  **Task 3 (Formatting):** Time to identify the Binary representation of Register 40005 (Value: 0xABCD).

**Analysis Strategy:**
-   **Compare:** Mean Time on Task (ModBusX vs. Competitor).
-   **Hypothesis:** ModBusX Search Bar will reduce navigation time by >50%.

---

## Appendix: Task List (for User)

**Context:** You are troubleshooting a PLC mapping with 500 registers.

**Task 1: Navigation**
*   **Goal:** Find Register **40450** and set its value to **123**.
*   *ModBusX Hint:* Try using the Search Bar.
*   *Competitor Hint:* Scroll or use 'Go to...'.

**Task 2: Addressing**
*   **Goal:** The engineer on the phone asks for the **Hex Protocol Address** (Base 0) of the current register. Switch the view mode to find it.
*   *ModBusX Hint:* Check the Toolbar.

**Task 3: Data Formats**
*   **Goal:** Read the **Binary** value of Register **40005**.
*   *ModBusX Hint:* Look at the bottom-right panel.
*   *Competitor Hint:* Open the display settings for that register/column.
