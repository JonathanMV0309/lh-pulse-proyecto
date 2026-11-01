/* =========================================================
   L&H SCORE
   DASHBOARD.JS
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    console.log("L&H SCORE - Dashboard JS iniciado");


    /* =====================================================
       1. GRÁFICA DE CONVERSIÓN DIARIA
       ===================================================== */

    const canvas = document.getElementById("conversionDiariaChart");

    if (canvas && typeof Chart !== "undefined") {

        const dias =
            window.dashboardConversionData?.dias || [];

        const traficoData =
            window.dashboardConversionData?.trafico || [];

        const facturasData =
            window.dashboardConversionData?.facturas || [];

        const conversionData =
            window.dashboardConversionData?.conversion || [];


        if (dias.length > 0) {

            /*
             * Evitar:
             * "Canvas is already in use"
             */

            const chartExistente =
                Chart.getChart(canvas);

            if (chartExistente) {
                chartExistente.destroy();
            }


            new Chart(canvas, {

                type: "line",

                data: {

                    labels: dias,

                    datasets: [

                        {
                            label: "Conversión (%)",

                            data: conversionData,

                            borderColor: "#2563eb",

                            backgroundColor:
                                "rgba(37, 99, 235, 0.1)",

                            borderWidth: 3,

                            pointRadius: 4,

                            pointHoverRadius: 6,

                            tension: 0.3,

                            fill: true,

                            yAxisID: "yConversion"
                        },

                        {
                            label: "Tráfico",

                            data: traficoData,

                            borderColor: "#94a3b8",

                            backgroundColor:
                                "rgba(148, 163, 184, 0.2)",

                            borderWidth: 2,

                            pointRadius: 3,

                            pointHoverRadius: 5,

                            tension: 0.3,

                            fill: true,

                            yAxisID: "yCantidad"
                        },

                        {
                            label: "Facturas",

                            data: facturasData,

                            borderColor: "#c5a880",

                            backgroundColor:
                                "rgba(197, 168, 128, 0.2)",

                            borderWidth: 2,

                            pointRadius: 3,

                            pointHoverRadius: 5,

                            tension: 0.3,

                            fill: true,

                            yAxisID: "yCantidad"
                        }

                    ]

                },

                options: {

                    responsive: true,

                    maintainAspectRatio: false,

                    interaction: {
                        mode: "index",
                        intersect: false
                    },

                    plugins: {

                        legend: {

                            position: "top",

                            labels: {
                                usePointStyle: true,
                                padding: 20
                            }

                        },

                        tooltip: {

                            callbacks: {

                                label: function (context) {

                                    const label =
                                        context.dataset.label || "";

                                    const value =
                                        context.parsed.y;

                                    if (
                                        context.dataset.label ===
                                        "Conversión (%)"
                                    ) {

                                        return (
                                            label +
                                            ": " +
                                            Number(value).toFixed(1) +
                                            "%"
                                        );

                                    }

                                    return (
                                        label +
                                        ": " +
                                        Number(value).toLocaleString()
                                    );

                                }

                            }

                        }

                    },

                    scales: {

                        yConversion: {

                            type: "linear",

                            position: "right",

                            beginAtZero: true,

                            title: {
                                display: true,
                                text: "Conversión (%)"
                            },

                            ticks: {

                                callback: function (value) {
                                    return value + "%";
                                }

                            },

                            grid: {
                                drawOnChartArea: false
                            }

                        },

                        yCantidad: {

                            type: "linear",

                            position: "left",

                            beginAtZero: true,

                            title: {
                                display: true,
                                text: "Cantidad"
                            }

                        },

                        x: {

                            title: {
                                display: true,
                                text: "Día del mes"
                            }

                        }

                    }

                }

            });

        }

    }


    /* =====================================================
       2. TOP 3 TIENDAS
       ===================================================== */

    iniciarAnimacionTop3Tiendas();

});


/* =========================================================
   FUNCIÓN PRINCIPAL TOP 3
   ========================================================= */

function iniciarAnimacionTop3Tiendas() {

    const overlay =
        document.getElementById("top3StoresOverlay");


    if (!overlay) {

        console.log(
            "Top 3 overlay no encontrado"
        );

        return;
    }


    /*
     * Mostrar solamente una vez por sesión
     */

    if (
        sessionStorage.getItem(
            "lhscore_top3_mostrado_sesion"
        ) === "1"
    ) {

        console.log(
            "La animación Top 3 ya se mostró en esta sesión."
        );

        return;
    }


    const tiendas =
        window.dashboardRankingTiendas || [];


    if (
        !Array.isArray(tiendas) ||
        tiendas.length === 0
    ) {

        console.log(
            "No existen datos para animar el Top 3"
        );

        return;
    }


    const top3 =
        tiendas
            .slice()
            .sort(function (a, b) {

                return (
                    Number(a.posicion || 999) -
                    Number(b.posicion || 999)
                );

            })
            .slice(0, 3);


    if (top3.length === 0) {
        return;
    }


    /*
     * Marcar la sesión solamente cuando realmente
     * tenemos información para mostrar.
     */

    sessionStorage.setItem(
        "lhscore_top3_mostrado_sesion",
        "1"
    );


    console.log(
        "Top 3 tiendas:",
        top3
    );


    /*
     * Crear partículas ANTES de mostrar overlay.
     */

    crearParticulasTop3();


    overlay.classList.add("active");


    ejecutarCeremoniaTop3(top3);

}


/* =========================================================
   CEREMONIA
   ========================================================= */

function ejecutarCeremoniaTop3(top3) {

    const stage =
        document.getElementById("top3Stage");

    const place =
        document.getElementById("top3Place");

    const storeImage =
        document.getElementById("top3StoreImage");

    const storeName =
        document.getElementById("top3StoreName");

    const storeCode =
        document.getElementById("top3StoreCode");

    const storeCompliance =
        document.getElementById(
            "top3StoreCompliance"
        );


    if (
        !stage ||
        !place ||
        !storeImage ||
        !storeName ||
        !storeCode ||
        !storeCompliance
    ) {

        console.warn(
            "Faltan elementos HTML del Top 3."
        );

        return;
    }


    let indice = 0;


    function mostrarTienda(tienda) {

        stage.classList.remove(
            "show-place",
            "show-store"
        );


        place.style.opacity = "0";

        storeName.style.opacity = "0";

        storeCode.style.opacity = "0";

        storeCompliance.style.opacity = "0";


        const posicion =
            Number(
                tienda.posicion ||
                indice + 1
            );


        const nombre =
            tienda.nombre ||
            "Tienda";


        const codigo =
            tienda.codigo ||
            "";


        const cumplimiento =
            Number(
                tienda.cumplimiento || 0
            ) * 100;


        if (posicion === 1) {

            place.innerHTML =
                "🥇 PRIMER LUGAR";

        }

        else if (posicion === 2) {

            place.innerHTML =
                "🥈 SEGUNDO LUGAR";

        }

        else {

            place.innerHTML =
                "🥉 TERCER LUGAR";

        }


        storeName.textContent =
            nombre;


        storeCode.textContent =
            codigo;


        storeCompliance.textContent =
            "Cumplimiento: " +
            cumplimiento.toFixed(1) +
            "%";


        cargarImagenTienda(
            storeImage,
            codigo,
            nombre
        );


        /*
         * Reiniciar animación CSS
         */

        void stage.offsetWidth;


        stage.classList.add(
            "show-place"
        );


        setTimeout(function () {

            stage.classList.add(
                "show-store"
            );

        }, 700);

    }


    /*
     * TERCER LUGAR
     */

    if (top3[2]) {

        indice = 2;

        mostrarTienda(top3[2]);

    }


    /*
     * SEGUNDO LUGAR
     */

    setTimeout(function () {

        if (!top3[1]) {
            return;
        }


        indice = 1;

        mostrarTienda(top3[1]);

    }, 4000);


    /*
     * PRIMER LUGAR
     */

    setTimeout(function () {

        if (!top3[0]) {
            return;
        }


        indice = 0;

        mostrarTienda(top3[0]);


        activarEfectoGanador();

    }, 8000);


    /*
     * PODIO FINAL
     */

    setTimeout(function () {

        mostrarPodioFinal(top3);

    }, 11500);

}


/* =========================================================
   CARGAR IMAGEN DE TIENDA
   ========================================================= */

function cargarImagenTienda(
    img,
    codigo,
    nombre
) {

    if (!img) {
        return;
    }


    const codigoLimpio =
        normalizarCodigoTienda(codigo);


    if (!codigoLimpio) {

        img.classList.add(
            "image-error"
        );

        return;
    }


    const rutas = [

        `/static/img/tiendas/${codigoLimpio}.jpg`,

        `/static/img/tiendas/${codigoLimpio}.jpeg`,

        `/static/img/tiendas/${codigoLimpio}.png`,

        `/static/img/tiendas/${codigoLimpio}.webp`,

        `/static/images/tiendas/${codigoLimpio}.jpg`,

        `/static/images/tiendas/${codigoLimpio}.jpeg`,

        `/static/images/tiendas/${codigoLimpio}.png`,

        `/static/images/tiendas/${codigoLimpio}.webp`

    ];


    let indice = 0;


    function intentar() {

        if (
            indice >= rutas.length
        ) {

            console.warn(
                "No se encontró imagen para:",
                codigoLimpio,
                nombre
            );


            img.classList.add(
                "image-error"
            );


            return;
        }


        img.classList.remove(
            "image-error"
        );


        img.src =
            rutas[indice];


        img.onerror =
            function () {

                indice++;

                intentar();

            };


        img.onload =
            function () {

                img.classList.remove(
                    "image-error"
                );

            };

    }


    intentar();

}


/* =========================================================
   NORMALIZAR CÓDIGO
   ========================================================= */

function normalizarCodigoTienda(codigo) {

    if (!codigo) {
        return "";
    }


    return String(codigo)

        .trim()

        .replace(/\s+/g, "-")

        .replace(
            /[^a-zA-Z0-9_-]/g,
            ""
        )

        .toUpperCase();

}


/* =========================================================
   PODIO FINAL
   ========================================================= */

function mostrarPodioFinal(top3) {

    const stage =
        document.getElementById(
            "top3Stage"
        );

    const podium =
        document.getElementById(
            "top3Podium"
        );

    const actions =
        document.getElementById(
            "top3Actions"
        );


    if (!stage || !podium) {
        return;
    }


    stage.style.display =
        "none";


    configurarPodio(
        top3[0],
        document.getElementById(
            "podiumImage1"
        ),
        document.getElementById(
            "podiumName1"
        ),
        document.getElementById(
            "podiumCompliance1"
        )
    );


    configurarPodio(
        top3[1],
        document.getElementById(
            "podiumImage2"
        ),
        document.getElementById(
            "podiumName2"
        ),
        document.getElementById(
            "podiumCompliance2"
        )
    );


    configurarPodio(
        top3[2],
        document.getElementById(
            "podiumImage3"
        ),
        document.getElementById(
            "podiumName3"
        ),
        document.getElementById(
            "podiumCompliance3"
        )
    );


    podium.classList.add(
        "visible"
    );


    if (actions) {

        setTimeout(function () {

            actions.classList.add(
                "visible"
            );

        }, 800);

    }

}


/* =========================================================
   CONFIGURAR PODIO
   ========================================================= */

function configurarPodio(
    tienda,
    imagen,
    nombre,
    cumplimiento
) {

    if (!tienda) {

        if (imagen) {

            imagen.style.visibility =
                "hidden";

        }


        if (nombre) {

            nombre.textContent =
                "";

        }


        if (cumplimiento) {

            cumplimiento.textContent =
                "";

        }


        return;
    }


    const codigo =
        tienda.codigo || "";


    const nombreTienda =
        tienda.nombre ||
        "Tienda";


    const porcentaje =
        Number(
            tienda.cumplimiento || 0
        ) * 100;


    if (nombre) {

        nombre.textContent =
            nombreTienda;

    }


    if (cumplimiento) {

        cumplimiento.textContent =
            porcentaje.toFixed(1) +
            "%";

    }


    if (imagen) {

        imagen.style.visibility =
            "visible";


        cargarImagenTienda(
            imagen,
            codigo,
            nombreTienda
        );

    }

}


/* =========================================================
   EFECTO GANADOR
   ========================================================= */

function activarEfectoGanador() {

    const overlay =
        document.getElementById(
            "top3StoresOverlay"
        );


    if (!overlay) {
        return;
    }


    overlay.classList.add(
        "winner-mode"
    );


    crearConfeti();

}


/* =========================================================
   PARTÍCULAS
   ========================================================= */

function crearParticulasTop3() {

    const container =
        document.getElementById(
            "top3Particles"
        );


    if (!container) {

        console.warn(
            "No existe #top3Particles en el HTML."
        );

        return;
    }


    /*
     * Limpiar partículas anteriores
     */

    container.innerHTML = "";


    /*
     * Asegurar que el contenedor funcione
     * aunque el CSS no se haya cargado
     * correctamente en otro PC.
     */

    container.style.position =
        "absolute";

    container.style.inset =
        "0";

    container.style.width =
        "100%";

    container.style.height =
        "100%";

    container.style.overflow =
        "hidden";

    container.style.pointerEvents =
        "none";

    container.style.zIndex =
        "5";


    /*
     * Crear 70 partículas
     */

    for (
        let i = 0;
        i < 70;
        i++
    ) {

        const particle =
            document.createElement(
                "span"
            );


        particle.className =
            "top3-particle";


        /*
         * Estilos esenciales INLINE.
         * Así las partículas aparecen también
         * en el otro PC aunque falte alguna regla CSS.
         */

        particle.style.position =
            "absolute";


        particle.style.display =
            "block";


        particle.style.left =
            Math.random() * 100 +
            "%";


        particle.style.bottom =
            "-10px";


        particle.style.width =
            (2 + Math.random() * 5) +
            "px";


        particle.style.height =
            particle.style.width;


        particle.style.borderRadius =
            "50%";


        particle.style.background =
            "rgba(216, 189, 131, 0.75)";


        particle.style.boxShadow =
            "0 0 8px rgba(216, 189, 131, 0.45)";


        particle.style.opacity =
            String(
                0.35 +
                Math.random() * 0.65
            );


        particle.style.pointerEvents =
            "none";


        particle.style.willChange =
            "transform, opacity";


        /*
         * Animación
         */

        const duracion =
            3 +
            Math.random() * 5;


        const retraso =
            Math.random() * 5;


        particle.style.animationName =
            "lhscoreParticleFloat";


        particle.style.animationDuration =
            duracion + "s";


        particle.style.animationDelay =
            retraso + "s";


        particle.style.animationIterationCount =
            "infinite";


        particle.style.animationTimingFunction =
            "ease-in-out";


        /*
         * Añadir al contenedor
         */

        container.appendChild(
            particle
        );

    }


    /*
     * Crear la animación directamente desde JS.
     *
     * Esto evita depender del CSS externo.
     */

    if (
        !document.getElementById(
            "lhscore-particles-animation"
        )
    ) {

        const style =
            document.createElement(
                "style"
            );


        style.id =
            "lhscore-particles-animation";


        style.textContent = `

            @keyframes lhscoreParticleFloat {

                0% {
                    transform:
                        translate3d(0, 0, 0)
                        scale(0.7);

                    opacity: 0;
                }

                15% {
                    opacity: 0.8;
                }

                50% {

                    transform:
                        translate3d(
                            ${Math.random() * 60 - 30}px,
                            -45vh,
                            0
                        )
                        scale(1);

                }

                85% {
                    opacity: 0.45;
                }

                100% {

                    transform:
                        translate3d(
                            ${Math.random() * 60 - 30}px,
                            -100vh,
                            0
                        )
                        scale(0.4);

                    opacity: 0;
                }

            }

        `;


        document.head.appendChild(
            style
        );

    }


    console.log(
        "Partículas Top 3 creadas correctamente:",
        container.children.length
    );

}


/* =========================================================
   CONFETI
   ========================================================= */

function crearConfeti() {

    const overlay =
        document.getElementById(
            "top3StoresOverlay"
        );


    if (!overlay) {
        return;
    }


    /*
     * Evitar duplicar confeti
     */

    overlay
        .querySelectorAll(
            ".lhscore-confetti"
        )
        .forEach(function (element) {

            element.remove();

        });


    for (
        let i = 0;
        i < 90;
        i++
    ) {

        const confeti =
            document.createElement(
                "div"
            );


        confeti.className =
            "lhscore-confetti";


        confeti.style.position =
            "absolute";


        confeti.style.top =
            "-20px";


        confeti.style.left =
            Math.random() * 100 +
            "%";


        confeti.style.width =
            (5 + Math.random() * 8) +
            "px";


        confeti.style.height =
            (8 + Math.random() * 14) +
            "px";


        confeti.style.background =
            obtenerColorConfeti();


        confeti.style.opacity =
            "0.9";


        confeti.style.zIndex =
            "100";


        confeti.style.pointerEvents =
            "none";


        confeti.style.borderRadius =
            "2px";


        const rotacion =
            Math.random() * 360;


        confeti.style.transform =
            `rotate(${rotacion}deg)`;


        const duracion =
            2.5 +
            Math.random() * 3;


        confeti.animate(

            [

                {

                    transform:
                        `translateY(0) rotate(${rotacion}deg)`,

                    opacity: 1

                },

                {

                    transform:
                        `translateY(110vh) rotate(${rotacion + 720}deg)`,

                    opacity: 0

                }

            ],

            {

                duration:
                    duracion * 1000,

                delay:
                    Math.random() * 800,

                easing:
                    "cubic-bezier(.2,.8,.3,1)",

                fill:
                    "forwards"

            }

        );


        overlay.appendChild(
            confeti
        );


        setTimeout(function () {

            if (
                confeti &&
                confeti.parentNode
            ) {

                confeti.remove();

            }

        }, (duracion + 2) * 1000);

    }


    console.log(
        "Confeti creado correctamente."
    );

}


/* =========================================================
   COLORES CONFETI
   ========================================================= */

function obtenerColorConfeti() {

    const colores = [

        "#d8bd83",

        "#e2c68f",

        "#ffffff",

        "#f5d98a",

        "#c5a880"

    ];


    return colores[
        Math.floor(
            Math.random() *
            colores.length
        )
    ];

}


/* =========================================================
   CERRAR ANIMACIÓN
   ========================================================= */

function cerrarAnimacionTop3() {

    const overlay =
        document.getElementById(
            "top3StoresOverlay"
        );


    if (!overlay) {
        return;
    }


    overlay.classList.add(
        "closing"
    );


    setTimeout(function () {

        if (
            overlay &&
            overlay.parentNode
        ) {

            overlay.remove();

        }

    }, 800);

}


/* =========================================================
   BOTONES
   ========================================================= */

document.addEventListener(
    "click",
    function (event) {

        const dashboardButton =
            event.target.closest(
                "#top3DashboardButton"
            );


        if (dashboardButton) {

            cerrarAnimacionTop3();

            return;

        }


        const homeButton =
            event.target.closest(
                "#top3HomeButton"
            );


        if (homeButton) {

            window.location.href =
                "/";

        }

    }
);


/* =========================================================
   PERMITIR ESCAPE
   ========================================================= */

document.addEventListener(
    "keydown",
    function (event) {

        if (
            event.key !== "Escape"
        ) {
            return;
        }


        const overlay =
            document.getElementById(
                "top3StoresOverlay"
            );


        if (
            overlay &&
            overlay.classList.contains(
                "active"
            )
        ) {

            cerrarAnimacionTop3();

        }

    }
);