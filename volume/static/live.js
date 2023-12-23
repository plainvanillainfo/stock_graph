
var trace_indices = JSON.parse(document.getElementById('trace_indices').textContent);
var plot_type = JSON.parse(document.getElementById('plot_type').textContent);

function add_data(plot_name, datetime, value) {
	var update_data = {
		x: [[datetime]],
		y: [[value]],
	};
	var index = trace_indices[plot_name];

	if (typeof index !== "undefined") {
		Plotly.extendTraces(PLOT_TARGET, update_data, [index]);
	}
}

function handle_ws_data(data) {
	if (data.all) {
		if (plot_type == "Volume") {
			add_data(data.plot_name, data.datetime, data.volume);
		} else {
			add_data(data.plot_name, data.datetime, data.slope);
		}

	} else {
		add_data(data.plot_name, data.datetime, data.value);
	}
}


function ws_connect() {
	var url = new URL('/volume_ws?channel=' + CHANNEL, window.location.href);
	url.protocol = url.protocol.replace('http', 'ws');
	var timeout = 250;
	var ws = new WebSocket(url);
	ws.onopen = function() {
		console.log("WebSocket connected");
		timeout = 250;
	};

	ws.onmessage = function(e) {
		handle_ws_data(JSON.parse(e.data));
	};

	ws.onclose = function(e) {
		console.log("WebSocket closed: Reconnecting");
		setTimeout(ws_connect, Math.min(10000, timeout += timeout));
	};

	ws.onerror = function(e) {
		console.log("WebSocket error: ", e.message);
		ws.close();
	};
}

if (LIVE) {
	ws_connect();
}
