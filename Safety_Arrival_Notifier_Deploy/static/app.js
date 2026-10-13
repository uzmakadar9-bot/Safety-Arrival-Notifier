// ============================================================
// SAFETY ARRIVAL NOTIFIER - MAIN JAVASCRIPT
// ============================================================

let map = null;
let destinationMarker = null;
let currentLocationMarker = null;
let gpsWatch = null;
let gpsInterval = null;

let dashboardInitialized = false;
let journeyActive = false;
let sendingLocation = false;
let startingJourney = false;


// ============================================================
// COMMON MESSAGE FUNCTION
// ============================================================

function showMessage(elementId, message, type = "success") {
    const element = document.getElementById(elementId);

    if (!element) return;

    element.textContent = message;
    element.className = "alert " + type;

    setTimeout(() => {
        element.classList.add("hidden");
    }, 4000);
}


// ============================================================
// GET JOURNEY STATUS
// ============================================================

async function getJourneyStatus() {

    const response = await fetch(
        "/api/journey/status",
        {
            cache: "no-store"
        }
    );

    if (!response.ok) {
        throw new Error(
            "Could not get journey status"
        );
    }

    return await response.json();
}


// ============================================================
// RISK UI
// ============================================================

function setRiskUI(score, level) {

    const badge =
        document.getElementById("riskBadge");

    const scoreElement =
        document.getElementById("scoreValue");

    score = Number(score) || 0;

    if (scoreElement) {

        scoreElement.textContent = score;
    }

    if (!badge) return;


    // Decide level from score.
    // This makes the colour reliable even if the backend
    // sends a slightly different status field.

    if (score >= 50) {

        level = "High Risk";

    } else if (score >= 25) {

        level = "Attention Needed";

    } else {

        level = "Normal";
    }


    badge.textContent = level;


    // Remove old risk classes

    badge.classList.remove(
        "normal",
        "attention",
        "high-risk"
    );


    // Add correct risk class

    if (level === "High Risk") {

        badge.classList.add(
            "high-risk"
        );

    } else if (
        level === "Attention Needed"
    ) {

        badge.classList.add(
            "attention"
        );

    } else {

        badge.classList.add(
            "normal"
        );
    }
}


// ============================================================
// MAP INITIALIZATION
// ============================================================

function initMap() {

    const mapElement =
        document.getElementById("map");


    if (!mapElement) {
        return;
    }


    // Prevent creating the map more than once

    if (map !== null) {
        return;
    }


    map =
        L.map("map")
        .setView(
            [19.0760, 72.8777],
            12
        );


    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                "&copy; OpenStreetMap contributors"
        }
    ).addTo(map);


    // --------------------------------------------------------
    // DESTINATION IS NOW ENTERED MANUALLY.
    //
    // The user types a destination name and the application
    // automatically selects that destination on the map when
    // Start Journey is clicked.
    // --------------------------------------------------------
}


// ============================================================
// SET DESTINATION
// ============================================================

function setDestination(
    lat,
    lng
) {

    const latInput =
        document.getElementById(
            "destinationLat"
        );


    const lngInput =
        document.getElementById(
            "destinationLng"
        );


    if (latInput) {

        latInput.value =
            Number(lat).toFixed(6);
    }


    if (lngInput) {

        lngInput.value =
            Number(lng).toFixed(6);
    }


    if (map) {

        // Remove previous destination marker

        if (destinationMarker) {

            map.removeLayer(
                destinationMarker
            );
        }


        // Create new destination marker

        destinationMarker =
            L.marker(
                [lat, lng]
            )
            .addTo(map)
            .bindPopup(
                "Selected Destination"
            )
            .openPopup();


        // Move map to destination

        map.setView(
            [lat, lng],
            15
        );
    }
}


// ============================================================
// USE CURRENT LOCATION
// ============================================================

function useCurrentLocation() {

    if (!navigator.geolocation) {

        showMessage(
            "flash",
            "GPS is not supported by this browser.",
            "error"
        );

        return;
    }


    const message =
        document.getElementById(
            "mapMessage"
        );


    if (message) {

        message.textContent =
            "Getting your current location...";
    }


    navigator.geolocation.getCurrentPosition(

        function (position) {

            const lat =
                position.coords.latitude;

            const lng =
                position.coords.longitude;


            // ------------------------------------------------
            // IMPORTANT:
            // Current location is the STARTING location.
            //
            // It is NOT written into the destination
            // latitude or longitude fields.
            // ------------------------------------------------

            if (map) {

                if (currentLocationMarker) {

                    map.removeLayer(
                        currentLocationMarker
                    );
                }


                currentLocationMarker =
                    L.marker(
                        [lat, lng]
                    )
                    .addTo(map)
                    .bindPopup(
                        "Your Current Location"
                    )
                    .openPopup();


                map.setView(
                    [lat, lng],
                    15
                );
            }


            if (message) {

                message.textContent =
                    "Your current location was detected automatically. Enter your destination below.";
            }
        },


        function (error) {

            let message =
                "Unable to get your location.";


            if (error.code === 1) {

                message =
                    "Location permission was denied. Please allow location access in your browser.";

            } else if (error.code === 2) {

                message =
                    "Your location could not be determined.";

            } else if (error.code === 3) {

                message =
                    "Location request timed out.";
            }


            showMessage(
                "flash",
                message,
                "error"
            );
        },


        {
            enableHighAccuracy: true,

            timeout: 15000,

            maximumAge: 0
        }
    );
}


// ============================================================
// GEOCODE MANUALLY ENTERED DESTINATION
// ============================================================

async function geocodeDestination(
    destinationName
) {

    const query =
        destinationName.trim();


    if (!query) {

        throw new Error(
            "Please enter a destination."
        );
    }


    const url =
        "https://nominatim.openstreetmap.org/search" +
        "?format=jsonv2" +
        "&limit=1" +
        "&q=" +
        encodeURIComponent(
            query
        );


    const response =
        await fetch(
            url,
            {
                headers: {
                    "Accept":
                        "application/json"
                }
            }
        );


    if (!response.ok) {

        throw new Error(
            "Could not search for the destination."
        );
    }


    const results =
        await response.json();


    if (
        !Array.isArray(results)
        ||
        results.length === 0
    ) {

        throw new Error(
            "Destination could not be found. Please enter a more specific destination name."
        );
    }


    const result =
        results[0];


    const lat =
        Number(
            result.lat
        );


    const lng =
        Number(
            result.lon
        );


    if (
        !Number.isFinite(lat)
        ||
        !Number.isFinite(lng)
    ) {

        throw new Error(
            "Invalid destination location received."
        );
    }


    return {
        lat: lat,
        lng: lng
    };
}


// ============================================================
// REFRESH DASHBOARD
// ============================================================

async function refreshDashboard() {

    try {

        const data =
            await getJourneyStatus();


        // ----------------------------------------------------
        // NO ACTIVE JOURNEY
        // ----------------------------------------------------

        if (!data.active) {

            journeyActive = false;


            const journeyStarted =
                document.getElementById(
                    "journeyStarted"
                );


            const stopButton =
                document.getElementById(
                    "stopJourneyBtn"
                );


            const destination =
                document.getElementById(
                    "destinationValue"
                );


            const eta =
                document.getElementById(
                    "etaValue"
                );


            const distance =
                document.getElementById(
                    "distanceValue"
                );


            const gps =
                document.getElementById(
                    "gpsText"
                );


            if (journeyStarted) {

                journeyStarted.textContent =
                    "Not Started";
            }


            if (stopButton) {

                stopButton.disabled =
                    true;
            }


            if (destination) {

                destination.textContent =
                    "—";
            }


            if (eta) {

                eta.textContent =
                    "—";
            }


            if (distance) {

                distance.textContent =
                    "—";
            }


            if (gps) {

                gps.textContent =
                    "GPS: waiting for journey";
            }


            setRiskUI(
                0,
                "Normal"
            );


            return;
        }


        // ----------------------------------------------------
        // ACTIVE JOURNEY
        // ----------------------------------------------------

        journeyActive = true;


        const journeyStarted =
            document.getElementById(
                "journeyStarted"
            );


        const stopButton =
            document.getElementById(
                "stopJourneyBtn"
            );


        const destination =
            document.getElementById(
                "destinationValue"
            );


        const eta =
            document.getElementById(
                "etaValue"
            );


        const distance =
            document.getElementById(
                "distanceValue"
            );


        const gps =
            document.getElementById(
                "gpsText"
            );


        if (journeyStarted) {

            journeyStarted.textContent =
                "Started";
        }


        if (stopButton) {

            stopButton.disabled =
                false;
        }


        if (destination) {

            destination.textContent =
                data.destination_name ||
                "—";
        }


        // ----------------------------------------------------
        // ETA
        // ----------------------------------------------------

        if (
            eta
            &&
            data.eta_minutes !== undefined
            &&
            data.eta_minutes !== null
        ) {

            const etaMinutes =
                Number(
                    data.eta_minutes
                );


            if (
                Number.isFinite(
                    etaMinutes
                )
            ) {

                eta.textContent =
                    etaMinutes +
                    " min";
            }
        }


        // ----------------------------------------------------
        // DISTANCE
        // ----------------------------------------------------

        if (
            distance
            &&
            data.distance_km !== undefined
            &&
            data.distance_km !== null
        ) {

            distance.textContent =
                Number(
                    data.distance_km
                ).toFixed(3) +
                " km";
        }


        // ----------------------------------------------------
        // GPS
        // ----------------------------------------------------

        if (gps) {

            if (
                data.latitude !== undefined
                &&
                data.longitude !== undefined
            ) {

                gps.textContent =
                    "GPS: " +
                    Number(
                        data.latitude
                    ).toFixed(6) +
                    ", " +
                    Number(
                        data.longitude
                    ).toFixed(6);

            } else {

                gps.textContent =
                    "GPS: waiting for location";
            }
        }


        // ----------------------------------------------------
        // RISK
        // ----------------------------------------------------

        setRiskUI(
            data.risk_score || 0,
            data.risk_status ||
            data.risk_level ||
            "Normal"
        );


    } catch (error) {

        console.error(
            "Dashboard refresh error:",
            error
        );
    }
}


// ============================================================
// SEND GPS LOCATION
// ============================================================

async function sendLocation(
    position
) {

    if (!journeyActive) {

        return;
    }


    // Prevent multiple GPS requests
    // at the same time

    if (sendingLocation) {

        return;
    }


    sendingLocation = true;


    try {

        const lat =
            position.coords.latitude;


        const lng =
            position.coords.longitude;


        const response =
            await fetch(
                "/api/journey/update",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        latitude: lat,

                        longitude: lng

                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                "GPS update failed"
            );
        }


        const data =
            await response.json();


        // ----------------------------------------------------
        // GPS TEXT
        // ----------------------------------------------------

        const gps =
            document.getElementById(
                "gpsText"
            );


        if (gps) {

            gps.textContent =
                "GPS: " +
                lat.toFixed(6) +
                ", " +
                lng.toFixed(6);
        }


        // ----------------------------------------------------
        // DISTANCE
        // ----------------------------------------------------

        const distance =
            document.getElementById(
                "distanceValue"
            );


        if (
            distance
            &&
            data.distance_km !== undefined
            &&
            data.distance_km !== null
        ) {

            distance.textContent =
                Number(
                    data.distance_km
                ).toFixed(3) +
                " km";
        }


        // ----------------------------------------------------
        // ETA
        // ----------------------------------------------------

        const eta =
            document.getElementById(
                "etaValue"
            );


        if (
            eta
            &&
            data.eta_minutes !== undefined
            &&
            data.eta_minutes !== null
        ) {

            const etaMinutes =
                Number(
                    data.eta_minutes
                );


            if (
                Number.isFinite(
                    etaMinutes
                )
            ) {

                eta.textContent =
                    etaMinutes +
                    " min";
            }
        }


        // ----------------------------------------------------
        // RISK
        // ----------------------------------------------------

        setRiskUI(
            data.risk_score || 0,
            data.risk_status ||
            data.risk_level ||
            "Normal"
        );


        // ----------------------------------------------------
        // ARRIVAL
        // ----------------------------------------------------

        if (data.arrived) {

            journeyActive = false;


            stopGPS();


            const journeyStarted =
                document.getElementById(
                    "journeyStarted"
                );


            const stopButton =
                document.getElementById(
                    "stopJourneyBtn"
                );


            if (journeyStarted) {

                journeyStarted.textContent =
                    "Safe Arrival";
            }


            if (stopButton) {

                stopButton.disabled =
                    true;
            }


            showMessage(
                "flash",
                "✅ Safe Arrival detected!",
                "success"
            );


            return;
        }


    } catch (error) {

        console.error(
            "Location update error:",
            error
        );


    } finally {

        sendingLocation = false;
    }
}


// ============================================================
// START GPS
// ============================================================

function startGPS() {

    // Stop any previous GPS tracking first

    stopGPS();


    if (!navigator.geolocation) {

        showMessage(
            "flash",
            "GPS is not supported by this browser.",
            "error"
        );

        return;
    }


    journeyActive = true;


    // Get location immediately

    navigator.geolocation.getCurrentPosition(

        function (position) {

            sendLocation(
                position
            );
        },


        function (error) {

            console.error(
                "GPS error:",
                error
            );
        },


        {
            enableHighAccuracy: true,

            timeout: 15000,

            maximumAge: 0
        }
    );


    // Then update every 10 seconds

    gpsInterval =
        setInterval(

            function () {

                if (!journeyActive) {

                    return;
                }


                navigator.geolocation.getCurrentPosition(

                    function (position) {

                        sendLocation(
                            position
                        );
                    },


                    function (error) {

                        console.error(
                            "GPS error:",
                            error
                        );
                    },


                    {
                        enableHighAccuracy:
                            true,

                        timeout:
                            15000,

                        maximumAge:
                            0
                    }
                );

            },

            10000
        );
}


// ============================================================
// STOP GPS
// ============================================================

function stopGPS() {

    if (gpsInterval !== null) {

        clearInterval(
            gpsInterval
        );

        gpsInterval =
            null;
    }


    if (gpsWatch !== null) {

        navigator.geolocation.clearWatch(
            gpsWatch
        );

        gpsWatch =
            null;
    }
}


// ============================================================
// START JOURNEY
// ============================================================

async function startJourney(
    event
) {

    event.preventDefault();


    // Prevent double-click /
    // duplicate requests

    if (startingJourney) {

        return;
    }


    startingJourney = true;


    const destinationName =
        document.getElementById(
            "destinationName"
        ).value.trim();


    const latInput =
        document.getElementById(
            "destinationLat"
        );


    const lngInput =
        document.getElementById(
            "destinationLng"
        );


    // --------------------------------------------------------
    // DESTINATION REQUIRED
    // --------------------------------------------------------

    if (!destinationName) {

        showMessage(
            "flash",
            "Please enter a destination.",
            "error"
        );


        startingJourney =
            false;


        return;
    }


    try {

        // ----------------------------------------------------
        // ALWAYS SEARCH THE DESTINATION NAME
        //
        // This is important because it prevents an old
        // destination's coordinates from being reused when
        // the user stops a journey and enters another one.
        // ----------------------------------------------------

        const mapMessage =
            document.getElementById(
                "mapMessage"
            );


        if (mapMessage) {

            mapMessage.textContent =
                "Searching for your destination...";
        }


        const result =
            await geocodeDestination(
                destinationName
            );


        const lat =
            Number(
                result.lat
            );


        const lng =
            Number(
                result.lng
            );


        // ----------------------------------------------------
        // AUTOMATICALLY FILL COORDINATES
        // ----------------------------------------------------

        if (latInput) {

            latInput.value =
                lat.toFixed(6);
        }


        if (lngInput) {

            lngInput.value =
                lng.toFixed(6);
        }


        // ----------------------------------------------------
        // AUTOMATICALLY SELECT DESTINATION ON MAP
        // ----------------------------------------------------

        setDestination(
            lat,
            lng
        );


        if (mapMessage) {

            mapMessage.textContent =
                "Destination selected automatically.";
        }


        // ----------------------------------------------------
        // START JOURNEY
        // ----------------------------------------------------

        const response =
            await fetch(
                "/api/journey/start",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        destination_name:
                            destinationName,

                        destination_lat:
                            lat,

                        destination_lng:
                            lng

                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.message ||
                data.error ||
                "Could not start journey."
            );
        }


        journeyActive =
            true;


        showMessage(
            "flash",
            "🚗 Journey Started Successfully!",
            "success"
        );


        // Update dashboard once

        await refreshDashboard();


        // Start live GPS tracking

        startGPS();


    } catch (error) {

        console.error(
            "Start journey error:",
            error
        );


        showMessage(
            "flash",
            error.message,
            "error"
        );


    } finally {

        startingJourney =
            false;
    }
}


// ============================================================
// STOP JOURNEY
// ============================================================

async function stopJourney() {

    if (!journeyActive) {

        return;
    }


    try {

        const response =
            await fetch(
                "/api/journey/stop",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    }
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                data.message ||
                "Could not stop journey."
            );
        }


        journeyActive =
            false;


        stopGPS();


        showMessage(
            "flash",
            "Journey stopped successfully.",
            "success"
        );


        await refreshDashboard();


    } catch (error) {

        console.error(
            "Stop journey error:",
            error
        );


        showMessage(
            "flash",
            error.message,
            "error"
        );
    }
}


// ============================================================
// DEMO RISK
// ============================================================

async function demoRisk(
    condition
) {

    try {

        const response =
            await fetch(
                "/api/demo/risk",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        condition:
                            condition

                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                data.message ||
                "Risk update failed."
            );
        }


        // IMPORTANT:
        // Backend uses risk_status.
        // Accept risk_level too for compatibility.

        setRiskUI(
            data.risk_score || 0,
            data.risk_status ||
            data.risk_level ||
            "Normal"
        );


        showMessage(
            "flash",
            "Risk status updated.",
            "success"
        );


    } catch (error) {

        console.error(
            "Demo risk error:",
            error
        );


        showMessage(
            "flash",
            error.message,
            "error"
        );
    }
}


// ============================================================
// SOS
// ============================================================

async function sendSOS() {

    try {

        const response =
            await fetch(
                "/api/journey/sos",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    }
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                data.message ||
                "SOS could not be sent."
            );
        }


        showMessage(
            "flash",
            "🚨 SOS alert recorded successfully.",
            "success"
        );


    } catch (error) {

        console.error(
            "SOS error:",
            error
        );


        showMessage(
            "flash",
            error.message,
            "error"
        );
    }
}


// ============================================================
// INITIALIZE DASHBOARD
// ============================================================

function initDashboard() {

    // ========================================================
    // VERY IMPORTANT
    // Prevent duplicate initialization
    // ========================================================

    if (dashboardInitialized) {

        console.log(
            "Dashboard already initialized."
        );

        return;
    }


    dashboardInitialized =
        true;


    console.log(
        "Safety Arrival Dashboard initialized."
    );


    // --------------------------------------------------------
    // MAP
    // --------------------------------------------------------

    initMap();


    // --------------------------------------------------------
    // INITIAL STATUS
    // --------------------------------------------------------

    refreshDashboard();


    // --------------------------------------------------------
    // CURRENT LOCATION BUTTON
    // --------------------------------------------------------

    const locateButton =
        document.getElementById(
            "locateMeBtn"
        );


    if (locateButton) {

        locateButton.addEventListener(
            "click",
            useCurrentLocation
        );
    }


    // --------------------------------------------------------
    // START JOURNEY FORM
    // --------------------------------------------------------

    const startForm =
        document.getElementById(
            "startJourneyForm"
        );


    if (startForm) {

        startForm.addEventListener(
            "submit",
            startJourney
        );
    }


    // --------------------------------------------------------
    // NEW DESTINATION TEXT INPUT
    //
    // Clear old coordinates when the user begins typing a
    // new destination. This prevents an old destination
    // from remaining in the coordinate fields.
    // --------------------------------------------------------

    const destinationInput =
        document.getElementById(
            "destinationName"
        );


    if (destinationInput) {

        destinationInput.addEventListener(
            "input",
            function () {

                const latInput =
                    document.getElementById(
                        "destinationLat"
                    );


                const lngInput =
                    document.getElementById(
                        "destinationLng"
                    );


                if (latInput) {

                    latInput.value =
                        "";
                }


                if (lngInput) {

                    lngInput.value =
                        "";
                }


                if (
                    destinationMarker
                    &&
                    map
                ) {

                    map.removeLayer(
                        destinationMarker
                    );


                    destinationMarker =
                        null;
                }
            }
        );
    }


    // --------------------------------------------------------
    // STOP JOURNEY
    // --------------------------------------------------------

    const stopButton =
        document.getElementById(
            "stopJourneyBtn"
        );


    if (stopButton) {

        stopButton.addEventListener(
            "click",
            stopJourney
        );
    }


    // --------------------------------------------------------
    // SOS
    // --------------------------------------------------------

    const sosButton =
        document.getElementById(
            "sosBtn"
        );


    if (sosButton) {

        sosButton.addEventListener(
            "click",
            sendSOS
        );
    }


    // --------------------------------------------------------
    // DEMO RISK BUTTONS
    // --------------------------------------------------------

    const riskButtons =
        document.querySelectorAll(
            ".demo-risk"
        );


    riskButtons.forEach(
        function (button) {

            button.addEventListener(
                "click",
                function () {

                    const condition =
                        button.dataset.condition;


                    demoRisk(
                        condition
                    );
                }
            );
        }
    );


    // --------------------------------------------------------
    // PREVENT GPS FROM CONTINUING
    // WHEN PAGE CLOSES
    // --------------------------------------------------------

    window.addEventListener(
        "beforeunload",
        function () {

            stopGPS();
        }
    );
}