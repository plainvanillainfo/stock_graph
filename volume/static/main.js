
for (var elem of document.getElementsByClassName('date-picker')) {
	var dp = new Datepicker(elem, {
		datesDisabled: [0, 6],
		format: 'yyyy-mm-dd',
		maxView: 2,
		todayBtn: true,
		weekStart: 1,
		todayHighlight: true,
		autohide: true,
	});
}
