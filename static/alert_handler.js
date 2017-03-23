// http://stackoverflow.com/questions/196972/convert-string-to-title-case-with-javascript
String.prototype.toProperCase = function () {
    return this.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
};

var generate_alert_panel = function() {
  // bc these get destroyed every time they are clicked!

  var panel = $("<div></div>")
    .addClass("alert alert-dismissable")
    .css('display', 'none')
    .append(
      $("<a></a>")
        .addClass("close")
        .attr("data-dismiss", "alert")
        .attr("href", "#")
        .attr("aria-label", "close")
        .html("&times;")
    )
    .append(
      $("<span></span>")
        .addClass("alert-message")
    )

    return panel
};

var alert_from_response = function() {

    var alert_type,
        resp_field,
        msg_printer
    ;

    var resp = arguments[0];
    var alert_wrapper = arguments[1];
    var opts = arguments[2] || {};
    
    // default msg_printer
    var default_msg_printer = function() {
        return resp_field.toProperCase() + " (" + resp[resp_field] + '): ' + resp['message'];
    };

    var general_msg_printer = opts['msg_printer'] || default_msg_printer;

    if ("success" in resp) {
        alert_type = resp_field = 'success';
        msg_printer = opts['msg_printer_success'] || general_msg_printer;
    } else if ("error" in resp) {
        alert_type = 'danger';
        resp_field = 'error';
        msg_printer = opts['msg_printer_error'] || general_msg_printer;
    } else if ("warning" in resp) {
        alert_type = resp_field = 'warning';
        msg_printer = opts['msg_printer_warning'] || general_msg_printer;
    } else if ("info" in resp ) {
        alert_type = resp_field = 'info';
        msg_printer = opts['msg_printer_info'] || general_msg_printer;
    } else {
        alert_type = 'danger';
        msg_printer = msg_printer || function() {
            return "Unknown error: " + JSON.stringify(resp);
        };
    }

    var alert_panel = generate_alert_panel();
    alert_panel
    .addClass("alert-" + alert_type)
      .show()
      .find('.alert-message')
      .append($("<div></div>")
          .append(msg_printer())
      )
    ;
    alert_wrapper.append(alert_panel);
}

var disable_element = function(el, reason) {
    var reason = reason || 'unknown reason.'

    el
        .prop("disabled", true)
        .addClass("disabled")
        .prop("title", "Disabled: " + reason)
};

var enable_element = function(el) {
    el
        .prop("disabled", false)
        .removeClass("disabled")
        // note: removeProp here would toggle the title to 'undefined'
        .removeAttr("title")
};

var alert_and_confirm = function() {

    var alert_wrapper = arguments[0];
    var opts = arguments[1] || {};
    var endpoint = opts['endpoint'];
    var alert_type = opts['alert_type'] || 'danger';
    var alert_msg = opts['alert_msg'] || 'Generic alert';
    var waiting_msg = opts['waiting_msg'] || 'Sending';
    var button_text = opts['button_text'] || 'Confirm';
    var close_on_response = opts['close_on_response'] || false;
    var close_on_confirm = opts['close_on_click'] || false;
    var close_on_success = opts['close_on_success'] || false;


    var source_el = opts['source_el'];
    var disable_until = opts['disable_until'];
    var alert_options = [
        'success', 'warning', 'info', 'danger'
    ];
    var disable_options = [
        'response_received', 'button_clicked', 'alert_cleared'
    ];

    if ( $.inArray(alert_type, alert_options) === -1 ) {
        var msg = "alert_type parameter ";
        msg += "'" + alert_type + "'";
        msg += " not recognized";

        console.warn( msg )
    }

    var confirm_before = opts['confirm_before'] || function() { return };
    var confirm_done = opts['confirm_done'] || function() { return };
    var confirm_done_success = opts['confirm_done_success'] || function() { return };

    // add custom msg printer here
    var confirm_alert_opts = opts['confirm_alert_opts'] || {};

    // validate disable until parameters or weird stuff will happen w
    // the button
    if (typeof disable_until !== 'undefined' && typeof source_el === 'undefined') {
        var msg = "source_el parameter required with disable_until";
        console.warn( msg )
        disable_until = undefined;
    };

    if (typeof disable_until !== 'undefined' && typeof endpoint === 'undefined') {
        var msg = "endpoint parameter required with disable_until";
        console.warn( msg )
        disable_until = undefined;
    };

    if (typeof disable_until !== 'undefined' && $.inArray(disable_until, disable_options) === -1 ) {
        var msg = "disable_until parameter ";
        msg += "'" + disable_until + "'";
        msg += " not recognized";

        console.warn( msg )
        disable_until = undefined;
    };

    // var alert_wrapper = $('#details-pane .alert-wrapper');
    var alert_panel = generate_alert_panel();

    if (typeof disable_until !== 'undefined') {
        disable_element(source_el, 'until ' + disable_until);
    };

    // button re-enabled in any mode if alert box is cleared
    if ( typeof disable_until !== 'undefined' )  {
        alert_panel
            .find('.close')
            .on('click', function() {
                enable_element(source_el)
            })    
    }

    alert_panel
      .addClass("alert-" + alert_type)
        .show()
    ;

    var alert_div = $("<div></div>")
        .append($("<span></span>")
            .append(alert_msg)
          )
          .append($("<span></span>")
              .addClass("waiting-alert")
              .text(" " + waiting_msg + "...")
              .hide()
          )
    ;

    if (typeof endpoint !== 'undefined') {
        var confirm_button = $("<button></button>")
            .attr("type", "button")
            .addClass("btn btn-" + alert_type)
            .css("margin-left", "20px")
            .text(button_text)
            .on('click', function() {
                disable_element($(this), "awaiting response.");
                if (close_on_confirm) {
                    alert_panel
                        .find('.close')
                        .click()
                }
                $.ajax({
                    "url": endpoint,
                    "beforeSend": function() {
                        confirm_before();
                        if (disable_until === 'button_clicked') {
                            enable_element(source_el)
                        }
                        confirm_button.parent().find('.waiting-alert').show();
                    }
                  }).done(function(d) {
                    enable_element(confirm_button);
                    if ($.inArray(disable_until, ['response_received', 'button_clicked']) !== -1) {
                        enable_element(source_el);
                    }
                    var resp = $.parseJSON(d);
                    confirm_button.parent().find('.waiting-alert').hide();
                    alert_from_response(resp, alert_wrapper, confirm_alert_opts);
                    confirm_done();
                    if ("success" in resp) {
                        confirm_done_success(resp);
                        if (close_on_success) {
                            alert_panel
                                .find('.close')
                                .click()    
                        }
                    }
                    if (close_on_response) {
                        alert_panel
                            .find('.close')
                            .click()
                    }
                  })
            })
        ;

        alert_div.append(confirm_button);
    }

    alert_panel.find('.alert-message').append(alert_div);
    alert_wrapper.append(alert_panel);
}