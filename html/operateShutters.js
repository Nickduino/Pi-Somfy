var pathname = window.location.href.split("/")[0].split("?")[0];
var baseurl = pathname.concat("cmd/");
var mymap;
var marker;
var config;
var modalCallerIconElement

GetStartupInfo(true);
$(document).ready(function() {
    resizeDiv();
    setupListeners();

});

window.onresize = function(event) {
    resizeDiv();
}

function resizeDiv() {
    vpw = $(window).width();
    vph = $(window).height();
    $('#accordion').css({'height': vph + 'px'});
    // $('#accordion').css({'width': vpw + 'px'});
    $('.panel-body').css({'height': vph-315 + 'px'});
    $('.table-wrapper').css({'height': vph-315 + 'px'});
    $('#mymap').css({'height': vph-400 + 'px'});
}

function GetStartupInfo(initMap)
{
    if (initMap == false) {
       $(".loader").addClass("is-active");
    }
    
    url = baseurl.concat("getConfig");
    $.getJSON(  url,
            {},
            function(result, status){
               config = result;
               setupTableShutters();
               setupTableSchedule();
               $(".loader").removeClass("is-active");
            });
}

function setupMap(lat, lng) {
    mymap = L.map('mymap').setView([lat, lng], 13);
    L.tileLayer('https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}{r}.png', {
        attribution: '<a href="https://wikimediafoundation.org/wiki/Maps_Terms_of_Use">Wikimedia</a>',
        minZoom: 1,
        maxZoom: 19
    }).addTo(mymap);
    // L.tileLayer('https://{s}.tile.openstreetmap.se/hydda/full/{z}/{x}/{y}.png', {
    //    maxZoom: 18,
    //    attribution: 'Tiles courtesy of <a href="http://openstreetmap.se/" target="_blank">OpenStreetMap Sweden</a> &mdash; Map data &copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    // }).addTo(mymap);
	
    marker = L.marker([lat, lng]).addTo(mymap)
    mymap.on('click', onMapClick);
    L.Control.geocoder({expand: 'touch', position:'topleft', defaultMarkGeocode: false}).on('markgeocode', function(e) {
        marker.setLatLng(e.geocode.center);
        mymap.setView(e.geocode.center, 15);
        marker.bindPopup("<center><b>Save as new Home Location?<b><br><input type=\"button\" value=\"Save\" onclick=\"setLocation('"+e.geocode.center.lat+"', '"+e.geocode.center.lng+"');\"></center>").openPopup();
    }).addTo(mymap);

}

function onMapClick(e) {
    marker.setLatLng(e.latlng)
    marker.bindPopup("<center><b>Save as new Home Location?<b><br><input type=\"button\" value=\"Save\" onclick=\"setLocation('"+e.latlng.lat+"', '"+e.latlng.lng+"');\"></center>").openPopup();
}

function locateUser() {
    mymap.locate({setView : true});
}

function prettyPrintSchedule(evt, shutters) {
   outstr = ""
   if (evt['active'] == "paused") {
      outstr += "<b>This schedule is currently paused</b><br>"
   }
   
   if (evt['repeatType'] == "weekday") {
      fullWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      weekend  = ['Sat', 'Sun'];
      weekday  = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
      if  (evt['repeatValue'].length === fullWeek.length && evt['repeatValue'].sort().every(function(value, index) { return value === fullWeek.sort()[index]})) {
         outstr += "Everyday, ";
      } else if (evt['repeatValue'].length === weekend.length && evt['repeatValue'].sort().every(function(value, index) { return value === weekend.sort()[index]})) {
         outstr += "On weekends, ";
      } else if (evt['repeatValue'].length === weekday.length && evt['repeatValue'].sort().every(function(value, index) { return value === weekday.sort()[index]})) {
         outstr += "During the week, ";
      } else {
         outstr += "Every "+evt['repeatValue'].join(", ")+", ";
      }
   } else if (evt['repeatType'] == "once") {
      outstr += "On "+evt['repeatValue']+", ";
   }
   
   if (evt['timeType'] == "clock") {
      outstr += "at "+evt['timeValue']+", ";
   } else if (evt['timeType'] == "astro") {
      if (evt['timeValue'].substring(0, 6) == "sunset") {
         if (evt['timeValue'].substring(6, 7) == "+") {
            outstr += evt['timeValue'].substring(7) + " minutes after sunset, ";
         } else if (evt['timeValue'].substring(6, 7) == "-") {
            outstr += evt['timeValue'].substring(7) + " minutes before sunset, ";
         } else {
            outstr += "at sunset, "
         }
      } else if (evt['timeValue'].substring(0, 7) == "sunrise") {
         if (evt['timeValue'].substring(7, 8) == "+") {
            outstr += evt['timeValue'].substring(8) + " minutes after sunrise, ";
         } else if (evt['timeValue'].substring(7, 8) == "-") {
            outstr += evt['timeValue'].substring(8) + " minutes before sunrise, ";
         } else {
            outstr += "at sunrise, ";
         }
      }
   }

   if (evt['shutterAction'].substring(0, 2) == "up") {
      outstr += "rise ";
      time = parseInt(evt['shutterAction'].substring(2));
      if (time > 0) {
         outstr += "for "+time+" seconds "
      } 
   } else if (evt['shutterAction'].substring(0, 4) == "down") {
      outstr += "lower ";
      time = parseInt(evt['shutterAction'].substring(4));
      if (time > 0) {
         outstr += "for "+time+" seconds "
      } 
   }

   if (evt['shutterIds'].length == 1) {
      outstr += "the shutter \""+shutters[evt['shutterIds'][0]]+"\".";
   } else {
      outstr += "these shutters \""+evt['shutterIds'].map(function(value) { return shutters[value] }).join("\", \"")+"\".";
   }

   return outstr;
}

function setLocation(lat, lng) {
    var url = baseurl.concat("setLocation");
      $.post(  url,
               {lat: lat, lng: lng},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      mymap.closePopup()
                   } else {
                      marker.bindPopup("<center><b>An error occured while saving.<br>Please try again</b></center>")
                   }
               }, "json");
}

function sendCommand(shutter, command, resetIcon) {
    var url = baseurl.concat(command);
      $.post(  url,
               {shutter: shutter},
               function(result, status){
                   resetIcon();
                   if ((status=="success") && (result.status == "OK")) {
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message});
                   }
               }, "json");
}

function addShutter(temp_id, name) {
    var url = baseurl.concat("addShutter");
      $.post(  url,
               {name: name},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      $("#shutters tbody tr:last-child").attr('name', result.id);
                      sendCommand(result.id, "program", function() {$('#program-new-shutter').modal('show');})
                   } else {
                      $(modalCallerIconElement).addClass("glyphicon-floppy-save").removeClass("glyphicon-refresh").removeClass("gly-spin");
        	      $(modalCallerIconElement).parents("tr").find(".save, .edit").toggle();
	              $(modalCallerIconElement).parents("tr").find(".delete").show();
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function editShutter(id, name, resetIcon) {
    var url = baseurl.concat("editShutter");
      $.post(  url,
               {id: id, name: name},
               function(result, status){
                   resetIcon();
                   if ((status=="success") && (result.status == "OK")) {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_INFO, title: 'Information', message:'Please Note:<br>If you are using the Alexa (Echo Speaker) integration, please read the following carefully.<br><br>Alexa does not allow to automatically rename your device. To rename your device on Alexa, please delete your current device and then ask Alexa to discover new devices.'});
                      GetStartupInfo(false);
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function programShutter(id) {
    var url = baseurl.concat("program");
      $.post(  url,
               {shutter: id},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_INFO, title: 'Information', message:'Program Code has been sent to Shutter.'});
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function deleteShutter(id) {
    var url = baseurl.concat("deleteShutter");
      $.post(  url,
               {id: id},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      GetStartupInfo(false);
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function addSchedule(temp_id, param) {
    var url = baseurl.concat("addSchedule");
      $.post(  url,
               param,
               function(result, status){
                   config.Schedule[result.id] = param;
                   evt = config.Schedule[result.id];
                   $(modalCallerIconElement).parents("tr").find('#scheduleText').html(prettyPrintSchedule(evt, config.Shutters));
                   $(modalCallerIconElement).parents("tr").find(".editbox").toggle();              
                   $(modalCallerIconElement).addClass("glyphicon-floppy-save").removeClass("glyphicon-refresh").removeClass("gly-spin");
        	   $(modalCallerIconElement).parents("tr").find(".save, .edit").toggle();
	           $(modalCallerIconElement).parents("tr").find(".delete").show();
                   if ((status=="success") && (result.status == "OK")) {
                      $(modalCallerIconElement).parents("tr").attr('name', result.id);
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message});
                   }
               }, "json");
}

function editSchedule(id, param, resetIcon) {
    var url = baseurl.concat("editSchedule");
      $.post(  url,
               param,
               function(result, status){
                   resetIcon();
                   if ((status=="success") && (result.status == "OK")) {
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function deleteSchedule(id) {
    var url = baseurl.concat("deleteSchedule");
      $.post(  url,
               {id: id},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}



function setupTableShutters () {
    $("#shutters").find("tr:gt(0)").remove();
    $("#manual").find("tr:gt(0)").remove();
    
    var shutterIds = Object.keys(config.Shutters);
    shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutter) {
        var row = '<tr name="'+shutter+'" rowtype="existing">' +
                     '<td name="name">'+config.Shutters[shutter]+'</td>' +
                     '<td class="td-action">' + $("#action_shutters").html() + '</td>' +
                  '</tr>';
        $("#shutters").append(row);

        var row = '<tr name="'+shutter+'">' +
                     '<td name="name">'+config.Shutters[shutter]+'</td>' +
                     '<td class="td-action">' + $("#action_manual").html() + '</td>' +
                  '</tr>';
        $("#manual").append(row);
    });
    $("#shuttersCount").text($("#shutters").find('tr').length-1);
}

function setupTableSchedule () {
    $("#schedule").find("tr:gt(0)").remove();

    var shutterIds = Object.keys(config.Shutters);
    $.each(Object.keys(config.Schedule), function(i, key) {
        evt = config.Schedule[key];
        var row = '<tr name="'+key+'" rowtype="existing">'+
                     '<td name="name">' + $("#description_schedule").html() + '</td>' +
		     '<td class="td-action">' + $("#action_schedule").html() + '</td>' + 
                  '</tr>';
    	$("#schedule").append(row);
        var thisRow =  $('#schedule tbody tr:last-child')
 
        thisRow.find('#scheduleText').html(prettyPrintSchedule(evt, config.Shutters));

        thisRow.find('#scheduleEdit #recordActive').prop('checked', evt['active'] == "active" ? true : false);  

        thisRow.find('#scheduleEdit .timeType').removeClass('in').hide();
        thisRow.find('#scheduleEdit .timeValue').removeClass('in').hide();
        if (evt['timeType'] == "clock") {
           thisRow.find('#scheduleEdit .timeType[data-optionvalue="clock"]').addClass('in').show();
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="clock"]').addClass('in').show();
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="clock"] input').val(evt['timeValue']);
        } else if ((evt['timeType'] == "astro") && (evt['timeValue'].substring(0, 7) == "sunrise")) {
           thisRow.find('#scheduleEdit .timeType[data-optionvalue="sunrise"]').addClass('in').show();
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunrise"]').addClass('in').show();
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunrise"] input').val(evt['timeValue'].substring(7).replace("+", "") || 0);
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunrise"] input.clockDelay').attr('data-slider-value', evt['timeValue'].substring(7).replace("+", "") || 0);
        } else if ((evt['timeType'] == "astro") && (evt['timeValue'].substring(0, 6) == "sunset")) {
           thisRow.find('#scheduleEdit .timeType[data-optionvalue="sunset"]').addClass('in').show();
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunset"]').addClass('in').show();
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunset"] input').val(evt['timeValue'].substring(6).replace("+", "") || 0);
           thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunset"] input.clockDelay').attr('data-slider-value', evt['timeValue'].substring(6).replace("+", "") || 0);
        }
        
        thisRow.find('#scheduleEdit .timeType[data-optionvalue="'+evt['timeType']+'"]').addClass('in').show();
        thisRow.find('#scheduleEdit .timeValue[data-optionvalue="'+evt['timeType']+'"]').addClass('in').show();
        thisRow.find('#scheduleEdit .timeValue[data-optionvalue="'+evt['timeType']+'"] input').val(evt['timeValue']);

        thisRow.find('#scheduleEdit .repeatType').removeClass('in').hide();
        thisRow.find('#scheduleEdit .repeatType[data-optionvalue="'+evt['repeatType']+'"]').addClass('in').show();
        thisRow.find('#scheduleEdit .repeatValue').removeClass('in').hide();
        thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="'+evt['repeatType']+'"]').addClass('in').show();
        if (evt['repeatType'] == "once") {
           thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="once"] input').val(evt['repeatValue']);
        } else if (evt['repeatType'] == "weekday") {
           thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="weekday"] input[type=checkbox]').prop('checked', false);
           for (var i in evt['repeatValue']) {
              var item = thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="weekday"] input[type=checkbox]#'+evt['repeatValue'][i])
              item.prop('checked', true);
              $(item).parent().css('color', '#ffffff').css('background', '#286090');
           }
        }
        if (evt['shutterAction'].substring(0, 2) == "up") {
           thisRow.find('#scheduleEdit .shutterActionUp').removeClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionDown').addClass("inactiveDirection");
           time = parseInt(evt['shutterAction'].substring(2));
           if (time > 0) {
              thisRow.find('.durationList').val(time)
           } else {
              thisRow.find('.durationList').val(0)           
           }
        } else if (evt['shutterAction'].substring(0, 4) == "down") {
           thisRow.find('#scheduleEdit .shutterActionDown').removeClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionUp').addClass("inactiveDirection");
           time = parseInt(evt['shutterAction'].substring(4));
           if (time > 0) {
              thisRow.find('.durationList').val(time)
           } else {
              thisRow.find('.durationList').val(0)           
           }
        }

        shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutter) {
           thisRow.find('.shuttersList').append('<option value="'+shutter+'"'+(evt['shutterIds'].includes(shutter) ? " selected" : "") +'>'+config.Shutters[shutter]+'</option>');
        });
        
    });
    $("#scheduleCount").text($("#schedule").find('tr').length-1);
    $('.editbox').hide();
    $('.editbox.in').show();

    $('[data-toggle="tooltip"]').tooltip();
    $('[rowtype="existing"] input[type=checkbox][data-toggle^=toggle]').bootstrapToggle();

    $('[rowtype="existing"] .clockDelay').bootstrapSlider();
    $('[rowtype="existing"] .clockDelay').on("slide", function(slideEvt) {$(this).parent().find("#clockDelayVal").val(slideEvt.value)});
    $('[rowtype="existing"] .clockpicker').clockpicker({placement: 'top', align: 'left', donetext: 'Done', autoclose: true});

    $('[rowtype="existing"] .date').datepicker({placement: 'top', autoclose: true, format: "yyyy/mm/dd"});    
    $('[rowtype="existing"] .weekDays-selector :checkbox').change(function() { $(this).parent().css('color', (this.checked) ? '#ffffff' : '#000000').css('background', (this.checked) ? '#286090' : '#f0f0f0')});
    
    $('[rowtype="existing"] .durationList').multiselect({dropUp: true, maxHeight: 100, buttonWidth: '75px'});
    $('[rowtype="existing"] .shuttersList').multiselect({dropUp: true, maxHeight: 100, includeSelectAllOption: true, buttonWidth: '130px', nonSelectedText: 'Please Select...', numberDisplayed: 1});
}


function clockDelayValUpdate(obj) {
   if ($(obj).val() !=  parseInt($(obj).val())){
      $(obj).val(0)
   } else if (parseInt($(obj).val()) > 300) {
      $(obj).val(300)
   } else if (parseInt($(obj).val()) < -300) {
      $(obj).val(-300)
   }
   $(obj).parent().find(".clockDelay").bootstrapSlider('setValue', $(obj).val());
}
    
function setupListeners() {
    $('#locateActions').find('a').on('click', function() { 
        locateUser();
    });

    $('[data-toggle="tooltip"]').tooltip();

    // Append table with add row form on add new button click
    $(".addShutters").click(function(){
	$(this).attr("disabled", "disabled");
        var index = $("#shutters tbody tr:last-child").index();
        var row = '<tr name="newkey_'+index+'" rowtype="new">' +
                      '<td name="name"><input type="text" class="form-control"></td>' +
   		      '<td class="td-action">' + $("#action_shutters").html() + '</td>' +
                  '</tr>';
    	$("#shutters").append(row);		

	$('#shutters tbody tr').eq(index + 1).find('.save, .edit').toggle();
        $('[data-toggle="tooltip"]').tooltip();
    });

    // Append table with add row form on add new button click
    $(".addSchedule").click(function(){
	$(this).attr("disabled", "disabled");
        var index = $("#schedule tbody tr:last-child").index();
        var row = '<tr name="newkey_'+index+'" rowtype="new">'+
                      '<td name="name">' + $("#description_schedule").html().replace("TEXT_0", "new scheudle") + '</td>' +
		          '<td class="td-action">' + $("#action_schedule").html() + '</td>' + 
                  '</tr>';
	$('#schedule').append(row)
	
	var thisRow =  $('#schedule tbody tr:last-child')
        thisRow.find('.editbox').toggle();
        thisRow.find('input[type=checkbox][data-toggle^=toggle]').bootstrapToggle();
        thisRow.find('.timeType').hide();
        thisRow.find('.timeType.in').show();
        thisRow.find('.timeValue').hide();
        thisRow.find('.timeValue.in').show();
        thisRow.find('.clockpicker').clockpicker({placement: 'top', align: 'left', donetext: 'Done', autoclose: true});
        thisRow.find('.clockDelay').bootstrapSlider();
        thisRow.find('.clockDelay').on('slide', function(slideEvt) { $(this).parent().find('#clockDelayVal').val(slideEvt.value)});
        thisRow.find('.repeatType').hide();
        thisRow.find('.repeatType.in').show();
        thisRow.find('.repeatValue').hide();
        thisRow.find('.repeatValue.in').show();
        thisRow.find('.date').datepicker({placement: 'top', autoclose: true, format: "yyyy/mm/dd"});
        thisRow.find('.weekDays-selector :checkbox').change(function() { $(this).parent().css('color', (this.checked) ? '#ffffff' : '#000000').css('background', (this.checked) ? '#286090' : '#f0f0f0')});
        var shutterIds = Object.keys(config.Shutters);
        shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutter) {
           thisRow.find('.shuttersList').append('<option value="'+shutter+'">'+config.Shutters[shutter]+'</option>');
        });
        thisRow.find('.durationList').val(0);
        thisRow.find('.durationList').multiselect({dropUp: true, maxHeight: 100, buttonWidth: '75px'});
        thisRow.find('.shuttersList').multiselect({dropUp: true, maxHeight: 100, includeSelectAllOption: true, buttonWidth: '130px', nonSelectedText: 'Please Select...', numberDisplayed: 1});

	$('#schedule tbody tr').eq(index + 1).find('.save, .edit').toggle();
        $('[data-toggle="tooltip"]').tooltip();
    });

    // Add row on add button click
    $(document).on("click", ".saveShutters", function(){
	var empty = false;
	var input = $(this).parents("tr").find('input[type="text"]');
	thisRow = $(this).parents("tr");

        input.each(function(){
	   if (!$(this).val()){
	       $(this).addClass("error");
	       empty = true;
	   } else {
               $(this).removeClass("error");
           }
        });
        $(this).parents("tr").find(".error").first().focus();
	if(!empty){
           var mydata = {id: $(this).parents("tr").attr('name')}
           var mytype = ($(this).parents("tr").attr("rowtype") == "new") ? "ADD" : "AMEND";
           input.each(function(){
    	      mydata[$(this).parent("td").attr('name')] = $(this).val();
	      $(this).parent("td").html($(this).val());
	   });			

	   $(this).parents("tr").attr("rowtype", "existing")
	   $(".addShutters").removeAttr("disabled");
           $("#shuttersCount").text($("#shutters").find('tr').length-1);
           if (mytype == "ADD") {
              modalCallerIconElement = $(this).find("i");
              $(modalCallerIconElement).toggleClass("glyphicon-floppy-save").toggleClass("glyphicon-refresh").addClass("gly-spin");
              addShutter(mydata.id, mydata.name);
           } else if (mytype == "AMEND") { 
              var iconElement = $(this).find("i");
              $(iconElement).toggleClass("glyphicon-floppy-save").toggleClass("glyphicon-refresh").addClass("gly-spin");
              editShutter(mydata.id, mydata.name, function(){
                 $(iconElement).toggleClass("glyphicon-floppy-save").toggleClass("glyphicon-refresh").removeClass("gly-spin")
    	         $(iconElement).parents("tr").find(".save, .edit").toggle();
	         $(iconElement).parents("tr").find(".delete").show();
              });
           }
           
	}		
    });

    // Add row on add button click
    $(document).on("click", ".saveSchedule", function(){
	var empty = false;
	var input = $(this).parents("tr").find('input[type="text"]');
	thisRow = $(this).parents("tr");
 
        repeatValueField = thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="once"] input[type="text"]');
        if ((thisRow.find("#scheduleEdit .repeatType.in").attr('data-optionvalue') == "once") && (!repeatValueField.val())) {
           repeatValueField.addClass("error");
           empty = true;
        } else if ((thisRow.find("#scheduleEdit .repeatType.in").attr('data-optionvalue') == "weekday") && (thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="weekday"] input:checked[type="checkbox"]').length == 0)) {
           thisRow.find('.weekDays-selector label').addClass("error");
           empty = true;
        } else {
           thisRow.find('.weekDays-selector label').removeClass("error");
           repeatValueField.removeClass("error");
        }

        timeValueField = thisRow.find('#scheduleEdit .timeValue[data-optionvalue="clock"] input[type="text"]')
        if ((thisRow.find("#scheduleEdit .timeType.in").attr('data-optionvalue') == "clock") && (!timeValueField.val())) {
           timeValueField.addClass("error");
           empty = true;
        } else {
           timeValueField.removeClass("error");
        }

        shutterIdsField = thisRow.find('#scheduleEdit .shuttersList');
        if (shutterIdsField.val().length == 0) {
           shutterIdsField.parent().find('.dropdown-toggle.btn').addClass("error");
           empty = true;
        } else {
           shutterIdsField.parent().find('.dropdown-toggle.btn').removeClass("error");
        }
        $(this).parents("tr").find(".error").first().focus();

        durationField = thisRow.find('#scheduleEdit .durationList');
        if (durationField.val().length == 0) {
           durationField.parent().find('.dropdown-toggle.btn').addClass("error");
           empty = true;
        } else {
           durationField.parent().find('.dropdown-toggle.btn').removeClass("error");
        }
        $(this).parents("tr").find(".error").first().focus();

        
	if(!empty){
           var mydata = {id: $(this).parents("tr").attr('name')}
           var mytype = ($(this).parents("tr").attr("rowtype") == "new") ? "ADD" : "AMEND";
           
           mydata['active'] = (thisRow.find('#scheduleEdit #recordActive').prop('checked') ? "active" : "paused");
           timeTypeTemp = thisRow.find('#scheduleEdit .timeType.in').attr('data-optionvalue')
           mydata['timeType'] = ((timeTypeTemp == "clock") ? "clock" : "astro");
           if (timeTypeTemp == "clock") {
              mydata['timeValue'] = timeValueField.val()
           } else if (timeTypeTemp == "sunrise") {
              var mytmp = thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunrise"] #clockDelayVal').val()
              if (parseInt(mytmp) == 0) {
                  mydata['timeValue'] = "sunrise"
              } else if (parseInt(mytmp) > 0) {
                  mydata['timeValue'] = "sunrise+"+parseInt(mytmp)
              } else if (parseInt(mytmp) < 0) {
                  mydata['timeValue'] = "sunrise"+parseInt(mytmp)
              }
           } else if (timeTypeTemp == "sunset") {
              var mytmp = thisRow.find('#scheduleEdit .timeValue[data-optionvalue="sunset"] #clockDelayVal').val()
              if (parseInt(mytmp) == 0) {
                  mydata['timeValue'] = "sunset"
              } else if (parseInt(mytmp) > 0) {
                  mydata['timeValue'] = "sunset+"+parseInt(mytmp)
              } else if (parseInt(mytmp) < 0) {
                  mydata['timeValue'] = "sunset"+parseInt(mytmp)
              }
           }
           mydata['repeatType'] = thisRow.find("#scheduleEdit .repeatType.in").attr('data-optionvalue');
           if (mydata['repeatType'] == "once") {
              mydata['repeatValue'] =repeatValueField.val();
           } else if (mydata['repeatType'] == "weekday") {
              var checkboxes =  thisRow.find('#scheduleEdit .repeatValue[data-optionvalue="weekday"] input[type="checkbox"]');
              var vals = [];
              for (var i=0, n=checkboxes.length;i<n;i++)  {
                  if (checkboxes[i].checked) {
                       vals.push(checkboxes[i].id);
                  }
              }
              mydata['repeatValue'] = vals;
           }
           mydata['shutterAction'] = thisRow.find('#scheduleEdit .shutterAction:not(.inactiveDirection)').attr('id');
           mydata['shutterIds'] = shutterIdsField.val();
           if (durationField.val() != 0) {
              mydata['shutterAction'] += durationField.val()
           }

	   $(this).parents("tr").attr("rowtype", "existing")
	   $(".addSchedule").removeAttr("disabled");
           $("#scheduleCount").text($("#schedule").find('tr').length-1);
           if (mytype == "ADD") {
              modalCallerIconElement = $(this).find("i");
              $(modalCallerIconElement).toggleClass("glyphicon-floppy-save").toggleClass("glyphicon-refresh").addClass("gly-spin");
              addSchedule(mydata.id, mydata);
           } else if (mytype == "AMEND") { 
              var iconElement = $(this).find("i");
              $(iconElement).toggleClass("glyphicon-floppy-save").toggleClass("glyphicon-refresh").addClass("gly-spin");
              editSchedule(mydata.id, mydata, function(){
                 config.Schedule[mydata.id] = mydata;
                 evt = config.Schedule[mydata.id];
                 $(iconElement).parents("tr").find('#scheduleText').html(prettyPrintSchedule(evt, config.Shutters));
                 $(iconElement).parents("tr").find(".editbox").toggle();              
                 $(iconElement).toggleClass("glyphicon-floppy-save").toggleClass("glyphicon-refresh").removeClass("gly-spin")
    	         $(iconElement).parents("tr").find(".save, .edit").toggle();
	         $(iconElement).parents("tr").find(".delete").show();
              });
                 
           }
           
	}		
    });

    $(document).on("click", ".timeTypeDown", function(){
         next = $(this).parent().find(".in").data("optionnext")
         $(this).parent().find(".timeType").removeClass("in").hide();
         $(this).parent().find('.timeType[data-optionvalue="'+next+'"]').addClass("in").show();
         $(this).parent().parent().find(".timeValue").removeClass("in").hide();
         $(this).parent().parent().find('.timeValue[data-optionvalue="'+next+'"]').addClass("in").show();
    });

    $(document).on("click", ".timeTypeUp", function(){
         prev = $(this).parent().find(".in").data("optionprev")
         $(this).parent().find(".timeType").removeClass("in").hide();
         $(this).parent().find('.timeType[data-optionvalue="'+prev+'"]').addClass("in").show();
         $(this).parent().parent().find(".timeValue").removeClass("in").hide();
         $(this).parent().parent().find('.timeValue[data-optionvalue="'+prev+'"]').addClass("in").show();
    });

    $(document).on("click", ".repeatTypeDown", function(){
         next = $(this).parent().find(".in").data("optionnext")
         $(this).parent().find(".repeatType").removeClass("in").hide();
         $(this).parent().find('.repeatType[data-optionvalue="'+next+'"]').addClass("in").show();
         $(this).parent().parent().find(".repeatValue").removeClass("in").hide();
         $(this).parent().parent().find('.repeatValue[data-optionvalue="'+next+'"]').addClass("in").show();
    });

    $(document).on("click", ".repeatTypeUp", function(){
         prev = $(this).parent().find(".in").data("optionprev")
         $(this).parent().find(".repeatType").removeClass("in").hide();
         $(this).parent().find('.repeatType[data-optionvalue="'+prev+'"]').addClass("in").show();
         $(this).parent().parent().find(".repeatValue").removeClass("in").hide();
         $(this).parent().parent().find('.repeatValue[data-optionvalue="'+prev+'"]').addClass("in").show();
    });

    $(document).on('click', ".shutterAction", function() {
      $(this).parent().find('.shutterAction').toggleClass("inactiveDirection");
    });


    // Edit row on edit button click
    $(document).on("click", ".editShutters", function(){		
        $(this).parents("tr").find("td:not(:last-child)").each(function(){
    	        $(this).html('<input type="text" class="form-control" value="' + $(this).text() + '">');
    	});		
	$(this).parents("tr").find(".save, .edit, .delete").toggle();
	$(".addShutters").attr("disabled", "disabled");
    });

    // Edit row on edit button click
    $(document).on("click", ".programShutters", function(){		
        programShutter($(this).parents("tr").attr('name'));
    });

    // Edit row on edit button click
    $(document).on("click", ".editSchedule", function(){		
        $(this).parents("tr").find('.editbox').toggle();
	$(this).parents("tr").find(".save, .edit, .delete").toggle();
	$(".addSchedule").attr("disabled", "disabled");
    });


    $(document).on("click", ".delete", function(){		
        modalCallerIconElement = $(this).find("i");
        $(modalCallerIconElement).toggleClass("glyphicon-trash").toggleClass("glyphicon-refresh").addClass("gly-spin");
    });

    
    $('#confirm-delete').on('hide.bs.modal', function(e) {
        $(modalCallerIconElement).addClass("glyphicon-trash").removeClass("glyphicon-refresh").removeClass("gly-spin");
    }); 
    
    $('#confirm-delete-ok').on("click", function(){
        var tableId = $(modalCallerIconElement).parents("table").attr('id');
        if ($(modalCallerIconElement).parents("tr").find('.edit').is(":visible")) {
             var rowId = $(modalCallerIconElement).parents("tr").attr('name');
             if (tableId == "shutters") {
                 deleteShutter(rowId);
             } else if (tableId == "schedule") {
                 deleteSchedule(rowId);
             }
        }
        $('#confirm-delete').modal('hide');
        $("#"+tableId+"Count").text($("#"+tableId).find('tr').length-2);
        $(modalCallerIconElement).parents("tr").remove();
     	$("#add_"+tableId).removeAttr("disabled");
    });


    $('#program-new-shutter').on('hide.bs.modal', function(e) {
        $(modalCallerIconElement).addClass("glyphicon-floppy-save").removeClass("glyphicon-refresh").removeClass("gly-spin");
        $(modalCallerIconElement).parents("tr").find(".save, .edit").toggle();
	$(modalCallerIconElement).parents("tr").find(".delete").show();
        GetStartupInfo(false);
    });
    
    $('#collapseOne').on('shown.bs.collapse', function () {
        if (mymap == undefined) {
            setupMap(config.Latitude, config.Longitude);
        }
    })

    $('#program-new-shutter-ok').on("click", function(){
        //  We are good, don't do anything. The hide.bs.modal event will take care of refreshing the main window
    });
    $('#program-new-shutter-try').on("click", function(){
        //  Try to programm again
        $('#program-new-shutter-try').text("Sending..")
        sendCommand($("#shutters tbody tr:last-child").attr('name'), "program", function() {$('#program-new-shutter-try').text("Try Programming again")})
    });
    
    $('#program-new-shutter-abort').on("click", function(){
        // Abort, delete the new shutter
        deleteShutter($("#shutters tbody tr:last-child").attr('name'));
        $('#program-new-shutter').modal('hide');
        // The hide.bs.modal event will take care of refreshing the main window
    });

    // Shutter Commands
    $(document).on("click", ".up", function(){		
        var key = $(this).parents("tr").attr('name');
        var iconElement = $(this).find("i");
        $(iconElement).toggleClass("glyphicon-arrow-up").toggleClass("glyphicon-refresh").addClass("gly-spin");
        sendCommand(key, "up", function(){$(iconElement).toggleClass("glyphicon-arrow-up").toggleClass("glyphicon-refresh").removeClass("gly-spin")});
    });
    $(document).on("click", ".down", function(){		
        var key = $(this).parents("tr").attr('name');
        var iconElement = $(this).find("i");
        $(iconElement).toggleClass("glyphicon-arrow-down").toggleClass("glyphicon-refresh").addClass("gly-spin");
        sendCommand(key, "down", function(){$(iconElement).toggleClass("glyphicon-arrow-down").toggleClass("glyphicon-refresh").removeClass("gly-spin")});
    });
    $(document).on("click", ".stop", function(){		
        var key = $(this).parents("tr").attr('name');
        var iconElement = $(this).find("i");
        $(iconElement).toggleClass("glyphicon-pause").toggleClass("glyphicon-refresh").addClass("gly-spin");
        sendCommand(key, "stop", function(){$(iconElement).toggleClass("glyphicon-pause").toggleClass("glyphicon-refresh").removeClass("gly-spin")});
    });

}
