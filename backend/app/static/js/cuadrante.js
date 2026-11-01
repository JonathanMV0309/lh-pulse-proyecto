document.addEventListener("DOMContentLoaded", function () {

    // ============================================================
    // ELEMENTOS DEL DOM
    // ============================================================

    const panelPersonas = document.getElementById("panelPersonas");
    const contenedorDias = document.getElementById("contenedorDias");

    const btnGuardar = document.getElementById("btnGuardarCuadrante");
    const btnAnterior = document.getElementById("btnSemanaAnterior");
    const btnSiguiente = document.getElementById("btnSemanaSiguiente");
    const btnActual = document.getElementById("btnSemanaActual");

    const kpiPersonas = document.getElementById("kpiPersonas");
    const kpiAsignaciones = document.getElementById("kpiAsignaciones");

    const contadorPersonas = document.getElementById("contadorPersonas");

    const rangoSemana = document.getElementById("rangoSemana");
    const tituloSemana = document.getElementById("tituloSemana");

    const estadoGuardado = document.getElementById("estadoGuardado");


    // ============================================================
    // VARIABLES
    // ============================================================

    let semanaActual = obtenerLunes(new Date());

    let datosArrastrados = null;

    let personasDisponibles = [];


    // ============================================================
    // FECHAS
    // ============================================================

    function obtenerLunes(fecha) {

        const d = new Date(fecha);

        const dia = d.getDay();

        const diferencia = dia === 0
            ? -6
            : 1 - dia;

        d.setDate(d.getDate() + diferencia);

        d.setHours(0, 0, 0, 0);

        return d;
    }


    function formatearFecha(fecha) {

        const yyyy = fecha.getFullYear();

        const mm = String(
            fecha.getMonth() + 1
        ).padStart(2, "0");

        const dd = String(
            fecha.getDate()
        ).padStart(2, "0");

        return `${yyyy}-${mm}-${dd}`;
    }


    function getSemana(fecha) {

        const lunes = obtenerLunes(fecha);

        const dias = [];

        for (let i = 0; i < 7; i++) {

            const dia = new Date(lunes);

            dia.setDate(
                lunes.getDate() + i
            );

            dias.push(dia);
        }

        return dias;
    }


    function obtenerIniciales(nombre) {

        if (!nombre) {
            return "?";
        }

        return nombre
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map(p =>
                p.charAt(0).toUpperCase()
            )
            .join("");
    }


    function capitalizar(texto) {

        if (!texto) {
            return "";
        }

        return texto.charAt(0).toUpperCase()
            + texto.slice(1);
    }


    // ============================================================
    // CABECERA DE SEMANA
    // ============================================================

    function actualizarCabeceraSemana(dias) {

        const inicio = dias[0];
        const fin = dias[6];


        const inicioTexto =
            inicio.toLocaleDateString(
                "es-CO",
                {
                    day: "2-digit",
                    month: "short"
                }
            );


        const finTexto =
            fin.toLocaleDateString(
                "es-CO",
                {
                    day: "2-digit",
                    month: "short"
                }
            );


        rangoSemana.textContent =
            `${inicioTexto} — ${finTexto}`;


        const inicioLargo =
            inicio.toLocaleDateString(
                "es-CO",
                {
                    day: "2-digit",
                    month: "long"
                }
            );


        const finLargo =
            fin.toLocaleDateString(
                "es-CO",
                {
                    day: "2-digit",
                    month: "long"
                }
            );


        tituloSemana.textContent =
            `${capitalizar(inicioLargo)} — ${capitalizar(finLargo)}`;
    }


    // ============================================================
    // ESTADO DEL GUARDADO
    // ============================================================

    function actualizarEstadoGuardado(tipo = "normal") {

        const texto =
            estadoGuardado.querySelector(
                "span:last-child"
            );


        estadoGuardado.classList.remove(
            "unsaved",
            "saved"
        );


        if (tipo === "unsaved") {

            estadoGuardado.classList.add(
                "unsaved"
            );

            texto.textContent =
                "Cambios sin guardar";

        }

        else if (tipo === "saved") {

            estadoGuardado.classList.add(
                "saved"
            );

            texto.textContent =
                "Cuadrante guardado";

        }

        else {

            texto.textContent =
                "Sin cambios";
        }
    }


    function marcarCambios() {

        actualizarEstadoGuardado(
            "unsaved"
        );
    }


    // ============================================================
    // CARGAR PERSONAS
    // ============================================================

    function cargarPersonas() {

        fetch(
            "/cuadrante/api/personas",
            {
                credentials: "same-origin"
            }
        )

        .then(res => {

            if (!res.ok) {

                throw new Error(
                    "No se pudieron cargar las personas."
                );
            }

            return res.json();
        })

        .then(personas => {

            personasDisponibles =
                Array.isArray(personas)
                    ? personas
                    : [];


            panelPersonas.innerHTML = "";


            kpiPersonas.textContent =
                personasDisponibles.length;


            contadorPersonas.textContent =
                personasDisponibles.length;


            if (!personasDisponibles.length) {

                panelPersonas.innerHTML = `
                    <div class="empty-people">
                        <i class="bi bi-person-x"></i>
                        No hay personas disponibles.
                    </div>
                `;

                return;
            }


            personasDisponibles.forEach(
                persona => {

                    const item =
                        document.createElement("div");


                    item.className =
                        "persona-disponible";


                    item.draggable = true;


                    item.dataset.personaId =
                        persona.id;


                    item.dataset.nombre =
                        persona.nombre;


                    item.dataset.tipo =
                        persona.tipo;


                    // ------------------------------------------------
                    // AVATAR
                    // ------------------------------------------------

                    const avatar =
                        document.createElement("div");


                    avatar.className =
                        "persona-avatar";


                    avatar.textContent =
                        obtenerIniciales(
                            persona.nombre
                        );


                    // ------------------------------------------------
                    // INFORMACIÓN
                    // ------------------------------------------------

                    const info =
                        document.createElement("div");


                    info.className =
                        "persona-info";


                    const nombre =
                        document.createElement("span");


                    nombre.className =
                        "persona-name";


                    nombre.textContent =
                        persona.nombre;


                    const tipo =
                        document.createElement("span");


                    tipo.className =
                        "persona-type";


                    tipo.textContent =
                        persona.tipo ||
                        "Personal";


                    info.appendChild(nombre);

                    info.appendChild(tipo);


                    // ------------------------------------------------
                    // INDICADOR DRAG
                    // ------------------------------------------------

                    const indicador =
                        document.createElement("i");


                    indicador.className =
                        "bi bi-grip-vertical drag-indicator";


                    // ------------------------------------------------
                    // ARMAR ELEMENTO
                    // ------------------------------------------------

                    item.appendChild(avatar);

                    item.appendChild(info);

                    item.appendChild(indicador);


                    // ------------------------------------------------
                    // DRAG START
                    // ------------------------------------------------

                    item.addEventListener(
                        "dragstart",
                        function (e) {

                            datosArrastrados = {

                                tipo: "nueva",

                                persona_id:
                                    persona.id,

                                nombre:
                                    persona.nombre,

                                tipo_persona:
                                    persona.tipo
                            };


                            e.dataTransfer.effectAllowed =
                                "copy";


                            e.dataTransfer.setData(
                                "text/plain",
                                JSON.stringify(
                                    datosArrastrados
                                )
                            );


                            requestAnimationFrame(
                                () => {

                                    item.classList.add(
                                        "arrastrando"
                                    );
                                }
                            );
                        }
                    );


                    // ------------------------------------------------
                    // DRAG END
                    // ------------------------------------------------

                    item.addEventListener(
                        "dragend",
                        function () {

                            item.classList.remove(
                                "arrastrando"
                            );

                            datosArrastrados = null;

                            limpiarZonasDestino();
                        }
                    );


                    panelPersonas.appendChild(
                        item
                    );
                }
            );
        })

        .catch(error => {

            console.error(
                "Error cargando personas:",
                error
            );


            panelPersonas.innerHTML = `
                <div class="empty-people text-danger">
                    <i class="bi bi-exclamation-circle"></i>
                    Error cargando las personas.
                </div>
            `;
        });
    }


    // ============================================================
    // LIMPIAR ZONAS DRAG
    // ============================================================

    function limpiarZonasDestino() {

        document
            .querySelectorAll(".zona-destino")
            .forEach(zona => {

                zona.classList.remove(
                    "zona-destino"
                );
            });
    }


    // ============================================================
    // CARGAR ASIGNACIONES
    // ============================================================

    function cargarAsignaciones(semana) {

        const dias =
            getSemana(semana);


        const inicio =
            formatearFecha(dias[0]);


        const fin =
            formatearFecha(dias[6]);


        actualizarCabeceraSemana(
            dias
        );


        fetch(
            `/cuadrante/api/asignaciones?inicio=${inicio}&fin=${fin}`,
            {
                credentials: "same-origin"
            }
        )

        .then(res => {

            if (!res.ok) {

                throw new Error(
                    "No se pudieron cargar las asignaciones."
                );
            }

            return res.json();
        })

        .then(asignaciones => {

            const datos =
                Array.isArray(asignaciones)
                    ? asignaciones
                    : [];


            renderizarDias(
                dias,
                datos
            );


            actualizarKpiAsignaciones(
                datos
            );


            actualizarEstadoGuardado(
                "normal"
            );
        })

        .catch(error => {

            console.error(
                "Error cargando asignaciones:",
                error
            );
        });
    }


    // ============================================================
    // KPI ASIGNACIONES
    // ============================================================

    function actualizarKpiAsignaciones(
        asignaciones
    ) {

        kpiAsignaciones.textContent =
            Array.isArray(asignaciones)
                ? asignaciones.length
                : 0;
    }


    // ============================================================
    // RENDERIZAR LOS 7 DÍAS
    // ============================================================

    function renderizarDias(
        dias,
        asignaciones
    ) {

        contenedorDias.innerHTML = "";


        const turnos = [
            "APERTURA",
            "CIERRE",
            "DESCANSO"
        ];


        const hoy =
            formatearFecha(
                new Date()
            );


        dias.forEach(dia => {

            const fechaStr =
                formatearFecha(dia);


            const esHoy =
                fechaStr === hoy;


            // ------------------------------------------------
            // CARD DEL DÍA
            // ------------------------------------------------

            const card =
                document.createElement("article");


            card.className =
                "day-card";


            if (esHoy) {

                card.classList.add(
                    "is-today"
                );
            }


            // ------------------------------------------------
            // HEADER
            // ------------------------------------------------

            const header =
                document.createElement("div");


            header.className =
                "day-header";


            const nombreDia =
                document.createElement("div");


            nombreDia.className =
                "day-name";


            nombreDia.textContent =
                dia.toLocaleDateString(
                    "es-CO",
                    {
                        weekday: "long"
                    }
                );


            const numeroDia =
                document.createElement("div");


            numeroDia.className =
                "day-number";


            numeroDia.textContent =
                dia.toLocaleDateString(
                    "es-CO",
                    {
                        day: "2-digit",
                        month: "short"
                    }
                );


            header.appendChild(
                nombreDia
            );


            header.appendChild(
                numeroDia
            );


            if (esHoy) {

                const badge =
                    document.createElement("span");


                badge.className =
                    "today-badge";


                badge.textContent =
                    "Hoy";


                header.appendChild(
                    badge
                );
            }


            // ------------------------------------------------
            // BODY
            // ------------------------------------------------

            const body =
                document.createElement("div");


            body.className =
                "day-body";


            // ------------------------------------------------
            // TURNOS
            // ------------------------------------------------

            turnos.forEach(
                turno => {

                    const turnoDiv =
                        document.createElement("div");


                    turnoDiv.className =
                        "turno-block";


                    const titulo =
                        document.createElement("div");


                    titulo.className =
                        `turno-title ${turno.toLowerCase()}`;


                    titulo.textContent =
                        turno;


                    const contenedorTurno =
                        document.createElement("div");


                    contenedorTurno.className =
                        "zona-asignacion";


                    contenedorTurno.dataset.fecha =
                        fechaStr;


                    contenedorTurno.dataset.turno =
                        turno;


                    // ------------------------------------------------
                    // FILTRAR ASIGNACIONES
                    // ------------------------------------------------

                    const asignacionesTurno =
                        asignaciones
                            .filter(a =>
                                a.fecha === fechaStr &&
                                a.turno === turno
                            )
                            .sort(
                                (a, b) =>
                                    (a.orden || 0) -
                                    (b.orden || 0)
                            );


                    // ------------------------------------------------
                    // ZONA VACÍA
                    // ------------------------------------------------

                    if (
                        !asignacionesTurno.length
                    ) {

                        mostrarZonaVacia(
                            contenedorTurno
                        );
                    }


                    // ------------------------------------------------
                    // DRAG OVER
                    // ------------------------------------------------

                    contenedorTurno.addEventListener(
                        "dragover",
                        function (e) {

                            e.preventDefault();

                            e.stopPropagation();


                            e.dataTransfer.dropEffect =
                                datosArrastrados?.tipo === "nueva"
                                    ? "copy"
                                    : "move";


                            contenedorTurno.classList.add(
                                "zona-destino"
                            );
                        }
                    );


                    // ------------------------------------------------
                    // DRAG LEAVE
                    // ------------------------------------------------

                    contenedorTurno.addEventListener(
                        "dragleave",
                        function (e) {

                            if (
                                !contenedorTurno.contains(
                                    e.relatedTarget
                                )
                            ) {

                                contenedorTurno.classList.remove(
                                    "zona-destino"
                                );
                            }
                        }
                    );


                    // ------------------------------------------------
                    // DROP
                    // ------------------------------------------------

                    contenedorTurno.addEventListener(
                        "drop",
                        function (e) {

                            e.preventDefault();

                            e.stopPropagation();


                            contenedorTurno.classList.remove(
                                "zona-destino"
                            );


                            let datos =
                                datosArrastrados;


                            if (!datos) {

                                try {

                                    const raw =
                                        e.dataTransfer.getData(
                                            "text/plain"
                                        );


                                    if (raw) {

                                        datos =
                                            JSON.parse(
                                                raw
                                            );
                                    }

                                }

                                catch (error) {

                                    console.error(
                                        "Error leyendo drag:",
                                        error
                                    );
                                }
                            }


                            if (!datos) {
                                return;
                            }


                            // ------------------------------------------------
                            // PERSONA NUEVA
                            // ------------------------------------------------

                            if (
                                datos.tipo === "nueva"
                            ) {

                                agregarAsignacion(
                                    datos,
                                    fechaStr,
                                    turno,
                                    null
                                );
                            }


                            // ------------------------------------------------
                            // ASIGNACIÓN EXISTENTE
                            // ------------------------------------------------

                            else if (
                                datos.tipo === "existente"
                            ) {

                                moverAsignacion(
                                    datos.asignacion_id,
                                    fechaStr,
                                    turno,
                                    e.clientY
                                );
                            }
                        }
                    );


                    // ------------------------------------------------
                    // CREAR CHIPS
                    // ------------------------------------------------

                    asignacionesTurno.forEach(
                        asignacion => {

                            const chip =
                                crearChip(
                                    asignacion
                                );


                            contenedorTurno.appendChild(
                                chip
                            );
                        }
                    );


                    turnoDiv.appendChild(
                        titulo
                    );


                    turnoDiv.appendChild(
                        contenedorTurno
                    );


                    body.appendChild(
                        turnoDiv
                    );
                }
            );


            card.appendChild(
                header
            );


            card.appendChild(
                body
            );


            contenedorDias.appendChild(
                card
            );
        });
    }


    // ============================================================
    // ZONA VACÍA
    // ============================================================

    function mostrarZonaVacia(
        contenedor
    ) {

        const texto =
            document.createElement("div");


        texto.className =
            "texto-zona-vacia";


        texto.textContent =
            "Arrastra aquí";


        contenedor.appendChild(
            texto
        );
    }


    function quitarZonaVacia(
        contenedor
    ) {

        const texto =
            contenedor.querySelector(
                ".texto-zona-vacia"
            );


        if (texto) {
            texto.remove();
        }
    }


    // ============================================================
    // CREAR CHIP DE ASIGNACIÓN
    // ============================================================

    function crearChip(
        asignacion
    ) {

        const chip =
            document.createElement("div");


        chip.className =
            "chip-asignacion";


        chip.draggable = true;


        chip.dataset.asignacionId =
            asignacion.id;


        chip.dataset.personaId =
            asignacion.persona_id;


        chip.dataset.nombre =
            asignacion.nombre;


        chip.dataset.tipo =
            asignacion.tipo || "";


        // ------------------------------------------------
        // AVATAR
        // ------------------------------------------------

        const avatar =
            document.createElement("div");


        avatar.className =
            "chip-avatar";


        avatar.textContent =
            obtenerIniciales(
                asignacion.nombre
            );


        // ------------------------------------------------
        // NOMBRE
        // ------------------------------------------------

        const nombreSpan =
            document.createElement("span");


        nombreSpan.className =
            "nombre-persona";


        nombreSpan.textContent =
            asignacion.nombre;


        // ------------------------------------------------
        // BOTÓN ELIMINAR
        // ------------------------------------------------

        const btnEliminar =
            document.createElement("button");


        btnEliminar.type =
            "button";


        btnEliminar.className =
            "btn-eliminar-asignacion";


        btnEliminar.title =
            "Eliminar asignación";


        btnEliminar.setAttribute(
            "aria-label",
            `Eliminar a ${asignacion.nombre}`
        );


        btnEliminar.innerHTML =
            "&times;";


        btnEliminar.addEventListener(
            "click",
            function (e) {

                e.preventDefault();

                e.stopPropagation();


                eliminarAsignacion(
                    asignacion.id
                );
            }
        );


        // ------------------------------------------------
        // ARMAR CHIP
        // ------------------------------------------------

        chip.appendChild(
            avatar
        );


        chip.appendChild(
            nombreSpan
        );


        chip.appendChild(
            btnEliminar
        );


        // ------------------------------------------------
        // DRAG START
        // ------------------------------------------------

        chip.addEventListener(
            "dragstart",
            function (e) {

                datosArrastrados = {

                    tipo: "existente",

                    asignacion_id:
                        asignacion.id,

                    persona_id:
                        asignacion.persona_id,

                    nombre:
                        asignacion.nombre
                };


                e.dataTransfer.effectAllowed =
                    "move";


                e.dataTransfer.setData(
                    "text/plain",
                    JSON.stringify(
                        datosArrastrados
                    )
                );


                requestAnimationFrame(
                    () => {

                        chip.classList.add(
                            "arrastrando"
                        );
                    }
                );


                e.stopPropagation();
            }
        );


        // ------------------------------------------------
        // DRAG END
        // ------------------------------------------------

        chip.addEventListener(
            "dragend",
            function () {

                chip.classList.remove(
                    "arrastrando"
                );


                datosArrastrados = null;


                limpiarZonasDestino();
            }
        );


        return chip;
    }


    // ============================================================
    // RECOLECTAR ASIGNACIONES
    // ============================================================

    function recolectarTodasLasAsignaciones() {

        const chips =
            document.querySelectorAll(
                ".chip-asignacion"
            );


        const asignaciones = [];


        chips.forEach(
            chip => {

                const contenedor =
                    chip.closest(
                        ".zona-asignacion"
                    );


                if (!contenedor) {
                    return;
                }


                const chipsZona =
                    Array.from(
                        contenedor.querySelectorAll(
                            ".chip-asignacion"
                        )
                    );


                const orden =
                    chipsZona.indexOf(
                        chip
                    );


                asignaciones.push({

                    id:
                        chip.dataset.asignacionId,

                    persona_id:
                        chip.dataset.personaId,

                    fecha:
                        contenedor.dataset.fecha,

                    turno:
                        contenedor.dataset.turno,

                    orden:
                        orden
                });
            }
        );


        return asignaciones;
    }


    // ============================================================
    // GUARDAR
    // ============================================================

    function guardarAsignaciones(
        asignaciones,
        mostrarMensaje = false
    ) {

        btnGuardar.disabled = true;


        return fetch(
            "/cuadrante/api/guardar",
            {
                method: "POST",

                credentials: "same-origin",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    asignaciones
                })
            }
        )

        .then(res => {

            if (!res.ok) {

                throw new Error(
                    "No se pudieron guardar las asignaciones."
                );
            }

            return res.json();
        })

        .then(data => {

            actualizarEstadoGuardado(
                "saved"
            );


            if (mostrarMensaje) {

                mostrarNotificacion(
                    data.message ||
                    "Cuadrante guardado correctamente."
                );
            }


            return cargarAsignaciones(
                semanaActual
            );
        })

        .catch(error => {

            console.error(
                "Error guardando asignaciones:",
                error
            );


            actualizarEstadoGuardado(
                "unsaved"
            );


            mostrarNotificacion(
                "No se pudieron guardar los cambios.",
                true
            );


            throw error;
        })

        .finally(() => {

            btnGuardar.disabled = false;
        });
    }


    // ============================================================
    // NOTIFICACIÓN
    // ============================================================

    function mostrarNotificacion(
        mensaje,
        error = false
    ) {

        const anterior =
            document.querySelector(
                ".toast-notificacion"
            );


        if (anterior) {
            anterior.remove();
        }


        const toast =
            document.createElement("div");


        toast.className =
            "toast-notificacion";


        if (error) {

            toast.style.background =
                "#fef2f2";

            toast.style.color =
                "#991b1b";

            toast.style.borderColor =
                "#fecaca";


            toast.innerHTML = `
                <span style="font-size:16px">
                    !
                </span>
                <span>
                    ${mensaje}
                </span>
            `;
        }

        else {

            toast.innerHTML = `
                <span>
                    ${mensaje}
                </span>
            `;
        }


        document.body.appendChild(
            toast
        );


        setTimeout(() => {

            toast.style.opacity =
                "0";

            toast.style.transform =
                "translateY(8px)";


            toast.style.transition =
                "opacity .2s ease, transform .2s ease";


            setTimeout(
                () => toast.remove(),
                220
            );

        }, 2500);
    }


    // ============================================================
    // AGREGAR ASIGNACIÓN
    // ============================================================

    function agregarAsignacion(
        datosPersona,
        fecha,
        turno,
        orden
    ) {

        const todas =
            recolectarTodasLasAsignaciones();


        const contenedor =
            document.querySelector(
                `.zona-asignacion[data-fecha="${fecha}"][data-turno="${turno}"]`
            );


        const nueva = {

            persona_id:
                datosPersona.persona_id,

            fecha:
                fecha,

            turno:
                turno,

            orden:
                contenedor
                    ? contenedor.querySelectorAll(
                        ".chip-asignacion"
                    ).length
                    : 0
        };


        todas.push(
            nueva
        );


        marcarCambios();


        guardarAsignaciones(
            todas,
            false
        );
    }


    // ============================================================
    // MOVER ASIGNACIÓN
    // ============================================================

    function moverAsignacion(
        asignacionId,
        nuevaFecha,
        nuevoTurno,
        clientY
    ) {

        const todas =
            recolectarTodasLasAsignaciones();


        const asignacion =
            todas.find(
                a =>
                    Number(a.id) ===
                    Number(asignacionId)
            );


        if (!asignacion) {

            console.error(
                "No se encontró la asignación."
            );

            return;
        }


        const indice =
            todas.indexOf(
                asignacion
            );


        todas.splice(
            indice,
            1
        );


        const contenedor =
            document.querySelector(
                `.zona-asignacion[data-fecha="${nuevaFecha}"][data-turno="${nuevoTurno}"]`
            );


        if (!contenedor) {
            return;
        }


        const chips =
            Array.from(
                contenedor.querySelectorAll(
                    ".chip-asignacion"
                )
            );


        let nuevoOrden =
            chips.length;


        // ------------------------------------------------
        // CALCULAR POSICIÓN
        // ------------------------------------------------

        if (
            clientY &&
            chips.length > 0
        ) {

            const posiciones =
                chips.map(
                    chip => {

                        const rect =
                            chip.getBoundingClientRect();


                        return {

                            chip,

                            centroY:
                                rect.top +
                                rect.height / 2
                        };
                    }
                );


            const despuesDe =
                posiciones.find(
                    p =>
                        clientY <
                        p.centroY
                );


            if (despuesDe) {

                nuevoOrden =
                    posiciones.indexOf(
                        despuesDe
                    );
            }
        }


        // ------------------------------------------------
        // ACTUALIZAR
        // ------------------------------------------------

        asignacion.fecha =
            nuevaFecha;


        asignacion.turno =
            nuevoTurno;


        asignacion.orden =
            nuevoOrden;


        todas.push(
            asignacion
        );


        marcarCambios();


        guardarAsignaciones(
            todas,
            false
        );
    }


    // ============================================================
    // ELIMINAR ASIGNACIÓN
    // ============================================================

    function eliminarAsignacion(
        asignacionId
    ) {

        if (
            !confirm(
                "¿Eliminar esta asignación?"
            )
        ) {

            return;
        }


        fetch(
            "/cuadrante/api/eliminar",
            {

                method: "POST",

                credentials:
                    "same-origin",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    id: asignacionId
                })
            }
        )

        .then(res => {

            if (!res.ok) {

                throw new Error(
                    "No se pudo eliminar la asignación."
                );
            }

            return res.json();
        })

        .then(() => {

            mostrarNotificacion(
                "Asignación eliminada."
            );


            cargarAsignaciones(
                semanaActual
            );
        })

        .catch(error => {

            console.error(
                "Error al eliminar:",
                error
            );


            mostrarNotificacion(
                "No se pudo eliminar la asignación.",
                true
            );
        });
    }


    // ============================================================
    // NAVEGACIÓN SEMANAL
    // ============================================================

    btnGuardar.addEventListener(
        "click",
        function () {

            const todas =
                recolectarTodasLasAsignaciones();


            guardarAsignaciones(
                todas,
                true
            );
        }
    );


    btnAnterior.addEventListener(
        "click",
        function () {

            semanaActual.setDate(
                semanaActual.getDate() - 7
            );


            cargarAsignaciones(
                semanaActual
            );
        }
    );


    btnSiguiente.addEventListener(
        "click",
        function () {

            semanaActual.setDate(
                semanaActual.getDate() + 7
            );


            cargarAsignaciones(
                semanaActual
            );
        }
    );


    btnActual.addEventListener(
        "click",
        function () {

            semanaActual =
                obtenerLunes(
                    new Date()
                );


            cargarAsignaciones(
                semanaActual
            );
        }
    );


    // ============================================================
    // INICIALIZACIÓN
    // ============================================================

    cargarPersonas();

    cargarAsignaciones(
        semanaActual
    );

});