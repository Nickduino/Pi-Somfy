/* ============================================================
   Pi-Somfy operateShutters.js
   Bootstrap-free – jQuery plugins + SVG icons
   ============================================================ */

// ===================== SVG ICON MAP =====================
var SVG_ICONS = {
    'gear-fill':      '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M9.405 1.05c-.413-1.4-2.397-1.4-2.81 0l-.1.34a1.464 1.464 0 0 1-2.105.872l-.31-.17c-1.283-.698-2.686.705-1.987 1.987l.169.311c.446.82.023 1.841-.872 2.105l-.34.1c-1.4.413-1.4 2.397 0 2.81l.34.1a1.464 1.464 0 0 1 .872 2.105l-.17.31c-.698 1.283.705 2.686 1.987 1.987l.311-.169a1.464 1.464 0 0 1 2.105.872l.1.34c.413 1.4 2.397 1.4 2.81 0l.1-.34a1.464 1.464 0 0 1 2.105-.872l.31.17c1.283.698 2.686-.705 1.987-1.987l-.169-.311a1.464 1.464 0 0 1 .872-2.105l.34-.1c1.4-.413 1.4-2.397 0-2.81l-.34-.1a1.464 1.464 0 0 1-.872-2.105l.17-.31c.698-1.283-.705-2.686-1.987-1.987l-.311.169a1.464 1.464 0 0 1-2.105-.872l-.1-.34zM8 10.93a2.929 2.929 0 1 1 0-5.86 2.929 2.929 0 0 1 0 5.858z"/></svg>',
    'list-ul':        '<svg viewBox="0 0 16 16"><circle cx="2" cy="3" r="1.3"/><circle cx="2" cy="8" r="1.3"/><circle cx="2" cy="13" r="1.3"/><rect x="5" y="2" width="10" height="2" rx=".8"/><rect x="5" y="7" width="10" height="2" rx=".8"/><rect x="5" y="12" width="10" height="2" rx=".8"/></svg>',
    'plus-lg':        '<svg viewBox="0 0 16 16"><rect x="7" y="1" width="2" height="14" rx=".8"/><rect x="1" y="7" width="14" height="2" rx=".8"/></svg>',
    'floppy':         '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/></svg>',
    'pencil':         '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/></svg>',
    'trash':          '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/><path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H5.5l.5-.5h4l.5.5h2.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/></svg>',
    'record-circle':  '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="8" r="3"/></svg>',
    'wrench':         '<svg viewBox="0 0 16 16"><path d="M1.3 10.3l5-5a4 4 0 015-4.8L9 2.8l-.2 2.4 2.4-.2 2.3-2.3a4 4 0 01-4.8 5l-5 5a1.2 1.2 0 01-1.7 0l-.7-.7a1.2 1.2 0 010-1.7z"/></svg>',
    'play-fill':      '<svg viewBox="0 0 16 16"><path d="M4 2.5l9 5.5-9 5.5z"/></svg>',
    'pause-fill':     '<svg viewBox="0 0 16 16"><rect x="3" y="2" width="3.5" height="12" rx=".8"/><rect x="9.5" y="2" width="3.5" height="12" rx=".8"/></svg>',
    'chevron-up':     '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,11 8,5 14,11"/></svg>',
    'chevron-down':   '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,5 8,11 14,5"/></svg>',
    'chevron-left':   '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11,2 5,8 11,14"/></svg>',
    'chevron-right':  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5,2 11,8 5,14"/></svg>',
    'clock':          '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 3.5a.5.5 0 0 0-1 0V8a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8 7.71V3.5z"/><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16zm7-8A7 7 0 1 1 1 8a7 7 0 0 1 14 0z"/></svg>',
    'calendar':       '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 0a.5.5 0 0 1 .5.5V1h8V.5a.5.5 0 0 1 1 0V1h1a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2h1V.5a.5.5 0 0 1 .5-.5zM1 4v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4H1z"/><path d="M6.5 7a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-9 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-9 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2z"/></svg>',
    'arrow-up':       '<svg viewBox="0 0 16 16"><path d="M8 1l5.5 6.5h-4V15h-3V7.5h-4z"/></svg>',
    'arrow-down':     '<svg viewBox="0 0 16 16"><path d="M8 15l5.5-6.5h-4V1h-3v7.5h-4z"/></svg>',
    'stop-fill':      '<svg viewBox="0 0 16 16"><rect x="3" y="3" width="10" height="10" rx="1"/></svg>',
    'arrow-down-up':  '<svg viewBox="0 0 16 16"><path d="M4.5 1l3 3.5H5.5v7h-2v-7H1.5L4.5 1zm7 14l-3-3.5h2v-7h2v7h2l-3 3.5z"/></svg>',
    'sort-numeric-down':'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v10m0 0l-3-3m3 3l3-3"/><text x="1" y="7" font-size="6" font-weight="bold" fill="currentColor" stroke="none">1</text><text x="1" y="14" font-size="6" font-weight="bold" fill="currentColor" stroke="none">2</text></svg>',
    'bullseye':       '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor"><circle cx="8" cy="8" r="6.5" stroke-width="1.2"/><circle cx="8" cy="8" r="4" stroke-width="1.2"/><circle cx="8" cy="8" r="1.8" fill="currentColor"/></svg>',
    'x-circle':       '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6.5"/><path d="M5.5 5.5l5 5M10.5 5.5l-5 5"/></svg>',
    'check-circle':   '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.5"/><polyline points="4.8,8.2 7,10.5 11.2,5.5"/></svg>',
    'arrow-down-circle':'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.5v6.5m0 0l-2.5-2.5m2.5 2.5l2.5-2.5"/></svg>',
    'arrow-up-circle':'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.5"/><path d="M8 11.5V5m0 0L5.5 7.5M8 5l2.5 2.5"/></svg>',
    'arrow-clockwise':'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8a5.5 5.5 0 019.5-3.5"/><path d="M14 1.5v3.5h-3.5"/><path d="M13.5 8a5.5 5.5 0 01-10 2.5"/></svg>',
    'sunrise':        '<svg viewBox="0 0 100 100" fill="currentColor"><polygon points="50,2 38,18 44,18 44,36 56,36 56,18 62,18"/><line x1="50" y1="62" x2="50" y2="46" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="42" y1="64" x2="34" y2="50" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="58" y1="64" x2="66" y2="50" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="34" y1="70" x2="22" y2="60" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="66" y1="70" x2="78" y2="60" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="M22,90 A28,28 0 0,1 78,90 z"/><rect x="8" y="92" width="84" height="5" rx="2.5"/></svg>',
    'sunset':         '<svg viewBox="0 0 100 100" fill="currentColor"><polygon points="44,2 56,2 56,20 62,20 50,36 38,20 44,20"/><line x1="50" y1="62" x2="50" y2="46" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="42" y1="64" x2="34" y2="50" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="58" y1="64" x2="66" y2="50" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="34" y1="70" x2="22" y2="60" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><line x1="66" y1="70" x2="78" y2="60" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="M22,90 A28,28 0 0,1 78,90 z"/><rect x="8" y="92" width="84" height="5" rx="2.5"/></svg>',
    'clock-type':     '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 3.5a.5.5 0 0 0-1 0V8a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8 7.71V3.5z"/><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16zm7-8A7 7 0 1 1 1 8a7 7 0 0 1 14 0z"/></svg>',
    'calendar-once':  '<svg viewBox="0 0 100 100" fill="currentColor"><rect x="5" y="15" width="90" height="80" rx="12" stroke="currentColor" stroke-width="6" fill="none"/><rect x="25" y="5" width="8" height="20" rx="4"/><rect x="67" y="5" width="8" height="20" rx="4"/><line x1="5" y1="35" x2="95" y2="35" stroke="currentColor" stroke-width="5"/><text x="50" y="78" font-size="42" font-weight="bold" text-anchor="middle" font-family="Arial,sans-serif">14</text></svg>',
    'calendar-week':  '<svg viewBox="0 0 100 100" fill="currentColor"><rect x="5" y="15" width="90" height="80" rx="12" stroke="currentColor" stroke-width="6" fill="none"/><rect x="25" y="5" width="8" height="20" rx="4"/><rect x="67" y="5" width="8" height="20" rx="4"/><line x1="5" y1="35" x2="95" y2="35" stroke="currentColor" stroke-width="5"/><text x="50" y="74" font-size="32" font-weight="bold" text-anchor="middle" font-family="Arial,sans-serif">Sun</text></svg>'
};

// ===================== ICON HELPERS =====================
function injectIcons(scope) {
    $(scope || document).find('.icon[data-icon]').each(function() {
        var name = $(this).attr('data-icon');
        if (!$(this).children('svg').length && SVG_ICONS[name]) {
            $(this).html(SVG_ICONS[name]);
        }
    });
}
function setIcon(el, name) {
    $(el).attr('data-icon', name).html(SVG_ICONS[name] || '');
}
// Auto-inject icons on DOM mutations
var _iconTimer;
new MutationObserver(function() {
    clearTimeout(_iconTimer);
    _iconTimer = setTimeout(function() { injectIcons(); }, 50);
}).observe(document.documentElement, { childList: true, subtree: true });

// ===================== MODAL PLUGIN =====================
(function($) {
    $.fn.modal = function(action) {
        return this.each(function() {
            var $m = $(this);
            if (action === 'show') {
                var $bd = $('<div class="modal-backdrop"></div>');
                $('body').append($bd);
                $m.css('display', 'flex');
                $bd[0].offsetHeight; // reflow
                $bd.addClass('show');
                $m.addClass('show');
                $m.trigger('show.modal');
            } else if (action === 'hide') {
                $m.trigger('hide.modal');
                $m.removeClass('show');
                $('.modal-backdrop').removeClass('show');
                setTimeout(function() {
                    $m.css('display', 'none');
                    $('.modal-backdrop').remove();
                    $m.trigger('hidden.modal');
                }, 300);
            } else if (action === 'dispose') {
                $m.off();
                $m.remove();
                $('.modal-backdrop').remove();
            }
        });
    };
    // Dismiss on backdrop click
    $(document).on('click', '.modal.show', function(e) {
        if (e.target === this) $(this).modal('hide');
    });
    // data-dismiss="modal"
    $(document).on('click', '[data-dismiss="modal"]', function() {
        $(this).closest('.modal').modal('hide');
    });
    // data-toggle="modal"
    $(document).on('click', '[data-toggle="modal"]', function(e) {
        e.preventDefault();
        var target = $(this).data('target') || $(this).attr('href');
        if (target) $(target).modal('show');
    });
})(jQuery);

// ===================== COLLAPSE PLUGIN =====================
(function($) {
    $.fn.collapse = function(action) {
        return this.each(function() {
            var $el = $(this);
            if (action === 'toggle') {
                $el.collapse($el.hasClass('show') ? 'hide' : 'show');
            } else if (action === 'show') {
                if ($el.hasClass('show')) return;
                var parentSel = $el.data('parent');
                if (parentSel) {
                    $(parentSel).find('.accordion-collapse.show').not($el).each(function() {
                        $(this).collapse('hide');
                    });
                }
                $el.addClass('show').hide().slideDown(350, function() {
                    $el.trigger('shown.collapse');
                });
                $('[data-target="#' + $el.attr('id') + '"]').removeClass('collapsed').attr('aria-expanded', 'true');
            } else if (action === 'hide') {
                if (!$el.hasClass('show')) return;
                $el.slideUp(350, function() {
                    $el.removeClass('show');
                    $el.trigger('hidden.collapse');
                });
                $('[data-target="#' + $el.attr('id') + '"]').addClass('collapsed').attr('aria-expanded', 'false');
            }
        });
    };
    // data-toggle="collapse"
    $(document).on('click', '[data-toggle="collapse"]', function(e) {
        e.preventDefault();
        var target = $(this).data('target');
        if (target) $(target).collapse('toggle');
    });
})(jQuery);

// ===================== TOOLTIP =====================
function removeOrphanedTooltips() {
    $('.custom-tooltip').remove();
}
function initTooltips(scope) {
    $(scope || document).find('[data-toggle="tooltip"],[data-tooltip="tooltip"]').each(function() {
        if ($(this).data('_tip_bound')) return;
        $(this).data('_tip_bound', true);
        var $el = $(this);

        function showTip() {
            removeOrphanedTooltips();
            var text = $el.attr('title');
            if (!text) return;
            $el.data('_orig_title', text).removeAttr('title');
            var $t = $('<div class="custom-tooltip"></div>').text(text);
            $('body').append($t);
            var r = $el[0].getBoundingClientRect();
            $t.css({ top: r.top - $t.outerHeight() - 6, left: r.left + (r.width - $t.outerWidth()) / 2 });
            $t.addClass('show');
            $el.data('_tip_el', $t);
        }

        function hideTip() {
            var $t = $el.data('_tip_el');
            if ($t) { $t.remove(); $el.data('_tip_el', null); }
            var ot = $el.data('_orig_title');
            if (ot) { $el.attr('title', ot); $el.removeData('_orig_title'); }
        }

        $el.on('mouseenter.tip', showTip);
        $el.on('mouseleave.tip click.tip', hideTip);
        $el[0].addEventListener('touchstart', function() {
            showTip();
            setTimeout(hideTip, 1500);
        }, { passive: true });
    });

    // Global safety nets — dismiss any lingering tooltip
    if (!initTooltips._globalBound) {
        initTooltips._globalBound = true;
        $(window).on('scroll.tip resize.tip', removeOrphanedTooltips);
        $(document).on('touchstart.tip', function(e) {
            if (!$(e.target).closest('[data-toggle="tooltip"],[data-tooltip="tooltip"]').length) removeOrphanedTooltips();
        });
    }
}

// ===================== TOGGLE (bootstrapToggle) =====================
(function($) {
    $.fn.bootstrapToggle = function() {
        return this.each(function() {
            var $cb = $(this);
            if ($cb.data('_toggle_init')) return;
            $cb.data('_toggle_init', true);
            var onL = $cb.data('onlabel') || 'On';
            var offL = $cb.data('offlabel') || 'Off';
            $cb.hide();
            var $wrap = $('<div class="custom-toggle"></div>');
            var $strip = $('<div class="toggle-strip"></div>');
            var $bar = $('<span class="toggle-bar"></span>');
            $strip.append('<span class="toggle-label-on">' + onL + '</span>');
            $strip.append('<span class="toggle-label-off">' + offL + '</span>');
            $wrap.append($strip, $bar);
            $cb.after($wrap);
            $wrap.prepend($cb);
            function upd() { $wrap.toggleClass('checked', $cb.prop('checked')); }
            upd();
            $wrap.on('click', function(e) {
                if ($(e.target).is('input')) return;
                $cb.prop('checked', !$cb.prop('checked')).trigger('change');
                upd();
            });
            $cb.on('change', upd);
        });
    };
})(jQuery);

// ===================== SLIDER (bootstrapSlider) =====================
(function($) {
    $.fn.bootstrapSlider = function(action, val) {
        if (action === 'setValue') {
            return this.each(function() {
                var d = $(this).data('_slider');
                if (d) d.setValue(parseInt(val) || 0);
            });
        }
        return this.each(function() {
            var $input = $(this);
            if ($input.data('_slider')) return;
            var min = parseInt($input.data('slider-min')) || 0;
            var max = parseInt($input.data('slider-max')) || 100;
            var step = parseInt($input.data('slider-step')) || 1;
            var value = parseInt($input.data('slider-value') || $input.val()) || 0;
            var inputW = $input[0].style.width || '130px';
            $input.hide();
            var $wrap = $('<div class="custom-slider-wrap"></div>').css('width', inputW);
            var $track = $('<div class="custom-slider-track"></div>');
            var $fill = $('<div class="custom-slider-fill"></div>');
            var $handle = $('<div class="custom-slider-handle"></div>');
            $track.append($fill, $handle);
            $wrap.append($track);
            $input.after($wrap);
            function pos(v) {
                var pct = ((v - min) / (max - min)) * 100;
                $handle.css('left', pct + '%');
                $fill.css('width', pct + '%');
                $input.val(v);
            }
            function sv(v) {
                v = Math.max(min, Math.min(max, Math.round(v / step) * step));
                pos(v);
            }
            pos(value);
            function onMove(e) {
                e.preventDefault();
                var rect = $track[0].getBoundingClientRect();
                var x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
                var pct = Math.max(0, Math.min(1, x / rect.width));
                var v = Math.round((min + pct * (max - min)) / step) * step;
                v = Math.max(min, Math.min(max, v));
                pos(v);
                $input.trigger({type: 'slide', value: v});
            }
            $track.on('mousedown touchstart', function(e) {
                onMove(e);
                $(document).on('mousemove.slider touchmove.slider', onMove);
                $(document).on('mouseup.slider touchend.slider', function() { $(document).off('.slider'); });
            });
            $input.data('_slider', { setValue: sv });
        });
    };
})(jQuery);

// ===================== CLOCKPICKER =====================
(function($) {
    $.fn.clockpicker = function(opts) {
        opts = opts || {};
        return this.each(function() {
            var $g = $(this);
            if ($g.data('_clockpicker')) return;
            var $inp = $g.find('input');
            var parts = ($inp.val() || '09:30').split(':');
            var cH = parseInt(parts[0]) || 9, cM = parseInt(parts[1]) || 30;
            var mode = 'hour'; // 'hour' or 'minute'

            var $pop = $('<div class="clockpicker-popup"></div>');
            // Header: shows selected time
            var $header = $('<div class="cp-header"><span class="cp-hval cp-active"></span><span class="cp-sep">:</span><span class="cp-mval"></span></div>');
            // Clock face
            var $face = $('<div class="cp-clock"><div class="cp-plate"><div class="cp-hand"></div><div class="cp-center"></div></div></div>');
            var $plate = $face.find('.cp-plate');
            var $hand = $face.find('.cp-hand');
            // Footer
            var $footer = $('<div class="cp-footer"><button type="button" class="cp-done">'+(opts.donetext||'Done')+'</button></div>');

            $pop.append($header).append($face).append($footer);
            $('body').append($pop);

            function pad(n) { return (n < 10 ? '0' : '') + n; }

            function buildHours() {
                mode = 'hour';
                $plate.find('.cp-num').remove();
                $header.find('.cp-hval').addClass('cp-active');
                $header.find('.cp-mval').removeClass('cp-active');
                // Outer ring: 1-12
                for (var i = 1; i <= 12; i++) {
                    var angle = (i * 30 - 90) * Math.PI / 180;
                    var x = 50 + 37 * Math.cos(angle);
                    var y = 50 + 37 * Math.sin(angle);
                    $plate.append('<div class="cp-num' + (i === cH % 12 || (i === 12 && cH === 0) ? ' cp-sel' : '') + '" data-val="' + i + '" style="left:' + x + '%;top:' + y + '%">' + i + '</div>');
                }
                // Inner ring: 0, 13-23
                var inner = [0, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23];
                for (var j = 0; j < 12; j++) {
                    var v = inner[j];
                    var a2 = ((j === 0 ? 12 : j) * 30 - 90) * Math.PI / 180;
                    var x2 = 50 + 23 * Math.cos(a2);
                    var y2 = 50 + 23 * Math.sin(a2);
                    $plate.append('<div class="cp-num cp-num-inner' + (v === cH ? ' cp-sel' : '') + '" data-val="' + v + '" style="left:' + x2 + '%;top:' + y2 + '%">' + pad(v) + '</div>');
                }
                setHand(cH);
            }

            function buildMinutes() {
                mode = 'minute';
                $plate.find('.cp-num').remove();
                $header.find('.cp-hval').removeClass('cp-active');
                $header.find('.cp-mval').addClass('cp-active');
                for (var i = 0; i < 12; i++) {
                    var v = i * 5;
                    var angle = (v * 6 - 90) * Math.PI / 180;
                    var x = 50 + 37 * Math.cos(angle);
                    var y = 50 + 37 * Math.sin(angle);
                    $plate.append('<div class="cp-num' + (v === cM ? ' cp-sel' : '') + '" data-val="' + v + '" style="left:' + x + '%;top:' + y + '%">' + pad(v) + '</div>');
                }
                setHand(cM);
            }

            function setHand(val) {
                var deg;
                if (mode === 'hour') {
                    deg = (val % 12) * 30;
                    var isInner = val === 0 || val > 12;
                    $hand.css({ transform: 'rotate(' + deg + 'deg)', height: isInner ? '25%' : '35%' });
                } else {
                    deg = val * 6;
                    $hand.css({ transform: 'rotate(' + deg + 'deg)', height: '35%' });
                }
            }

            function updDisplay() {
                $header.find('.cp-hval').text(pad(cH));
                $header.find('.cp-mval').text(pad(cM));
            }

            function updInput() {
                $inp.val(pad(cH) + ':' + pad(cM));
            }

            updDisplay();

            // Click on number
            $plate.on('click', '.cp-num', function() {
                var v = parseInt($(this).data('val'));
                if (mode === 'hour') {
                    cH = v;
                    updDisplay();
                    $plate.find('.cp-num').removeClass('cp-sel');
                    $(this).addClass('cp-sel');
                    setHand(cH);
                    // Auto-advance to minutes after short delay
                    setTimeout(buildMinutes, 300);
                    updDisplay();
                } else {
                    cM = v;
                    updDisplay();
                    $plate.find('.cp-num').removeClass('cp-sel');
                    $(this).addClass('cp-sel');
                    setHand(cM);
                }
                updInput();
            });

            // Click on plate for finer minute selection
            $plate.on('click', function(e) {
                if ($(e.target).hasClass('cp-num') || $(e.target).hasClass('cp-hand') || $(e.target).hasClass('cp-center')) return;
                if (mode !== 'minute') return;
                var rect = $plate[0].getBoundingClientRect();
                var cx = rect.left + rect.width / 2;
                var cy = rect.top + rect.height / 2;
                var dx = e.clientX - cx, dy = e.clientY - cy;
                var angle = Math.atan2(dy, dx) * 180 / Math.PI + 90;
                if (angle < 0) angle += 360;
                cM = Math.round(angle / 6) % 60;
                updDisplay(); updInput();
                $plate.find('.cp-num').removeClass('cp-sel');
                $plate.find('.cp-num').each(function() {
                    if (parseInt($(this).data('val')) === cM) $(this).addClass('cp-sel');
                });
                setHand(cM);
            });

            // Header clicks to switch mode
            $header.find('.cp-hval').on('click', function() { buildHours(); updDisplay(); });
            $header.find('.cp-mval').on('click', function() { buildMinutes(); updDisplay(); });

            function show() {
                var p2 = ($inp.val() || '09:30').split(':');
                cH = parseInt(p2[0]) || 0; cM = parseInt(p2[1]) || 0;
                updDisplay();
                buildHours();
                var r = $g[0].getBoundingClientRect();
                $pop.css('display', 'flex');
                var t = r.bottom + 4;
                if (t + $pop.outerHeight() > window.innerHeight) t = r.top - $pop.outerHeight() - 4;
                var l = r.left;
                if (l + $pop.outerWidth() > window.innerWidth) l = window.innerWidth - $pop.outerWidth() - 8;
                $pop.css({ top: t, left: l }).addClass('show');
            }

            function hide() { $pop.removeClass('show').css('display', ''); updInput(); }

            $g.find('.input-group-addon, .input-group-text').on('click', function() { $pop.hasClass('show') ? hide() : show(); });
            $inp.on('click', function() { if (!$pop.hasClass('show')) show(); });
            $pop.find('.cp-done').on('click', hide);
            $(document).on('mousedown', function(e) {
                if (!$(e.target).closest($pop).length && !$(e.target).closest($g).length) hide();
            });
            $g.data('_clockpicker', true);
        });
    };
})(jQuery);

// ===================== DATEPICKER =====================
(function($) {
    $.fn.datepicker = function(opts) {
        opts = opts || {};
        return this.each(function() {
            var $g = $(this);
            if ($g.data('_datepicker')) return;
            var $inp = $g.find('input');
            var fmt = opts.format || 'yyyy/mm/dd';
            var now = new Date(), cY = now.getFullYear(), cM = now.getMonth();
            var sel = null;
            var $pop = $('<div class="datepicker-popup"></div>');
            $('body').append($pop);
            function parse(s) {
                if (!s) return null;
                var p = s.indexOf('/')>-1 ? s.split('/') : s.split('-');
                if (p.length<3) return null;
                if (fmt === 'dd-mm-yyyy') return new Date(+p[2], p[1]-1, +p[0]);
                return new Date(+p[0], p[1]-1, +p[2]);
            }
            function format(d) {
                var dd = (d.getDate()<10?'0':'')+d.getDate();
                var mm = ((d.getMonth()+1)<10?'0':'')+(d.getMonth()+1);
                var yy = d.getFullYear();
                if (fmt === 'dd-mm-yyyy') return dd+'-'+mm+'-'+yy;
                return yy+'/'+mm+'/'+dd;
            }
            function render() {
                var first = new Date(cY,cM,1), dow = (first.getDay()+6)%7;
                var dim = new Date(cY,cM+1,0).getDate();
                var prev = new Date(cY,cM,0).getDate();
                var mons = ['January','February','March','April','May','June','July','August','September','October','November','December'];
                var h = '<div class="dp-header"><button type="button" class="dp-prev">\u2039</button><span class="dp-title">'+mons[cM]+' '+cY+'</span><button type="button" class="dp-next">\u203A</button></div><div class="dp-body"><div class="dp-grid">';
                var dw = ['Mo','Tu','We','Th','Fr','Sa','Su'];
                for (var i=0;i<7;i++) h+='<div class="dp-dow">'+dw[i]+'</div>';
                for (var i=dow-1;i>=0;i--) h+='<div class="dp-day other-month">'+(prev-i)+'</div>';
                var td = new Date();
                for (var d=1;d<=dim;d++) {
                    var c='dp-day';
                    if (d===td.getDate()&&cM===td.getMonth()&&cY===td.getFullYear()) c+=' today';
                    if (sel&&d===sel.getDate()&&cM===sel.getMonth()&&cY===sel.getFullYear()) c+=' selected';
                    h+='<div class="'+c+'" data-day="'+d+'">'+d+'</div>';
                }
                var tot=dow+dim, rem=(7-(tot%7))%7;
                for (var i=1;i<=rem;i++) h+='<div class="dp-day other-month">'+i+'</div>';
                h+='</div></div>';
                $pop.html(h);
                $pop.find('.dp-prev').on('click',function(){cM--;if(cM<0){cM=11;cY--;}render();});
                $pop.find('.dp-next').on('click',function(){cM++;if(cM>11){cM=0;cY++;}render();});
                $pop.find('.dp-day[data-day]').on('click',function(){
                    sel=new Date(cY,cM,+$(this).data('day'));
                    $inp.val(format(sel));
                    if(opts.autoclose)hidePop();else render();
                });
            }
            function showPop(){
                var p2=parse($inp.val()); if(p2){sel=p2;cY=p2.getFullYear();cM=p2.getMonth();}
                render();
                var r=$g[0].getBoundingClientRect();
                $pop.css('display','flex');
                var t=r.bottom+4; if(t+$pop.outerHeight()>window.innerHeight)t=r.top-$pop.outerHeight()-4;
                var l=r.left; if(l+$pop.outerWidth()>window.innerWidth)l=window.innerWidth-$pop.outerWidth()-8;
                $pop.css({top:t,left:l}).addClass('show');
            }
            function hidePop(){ $pop.removeClass('show').css('display',''); }
            $g.find('.input-group-addon, .input-group-text').on('click',function(){ $pop.hasClass('show')?hidePop():showPop(); });
            $(document).on('mousedown',function(e){ if(!$(e.target).closest($pop).length&&!$(e.target).closest($g).length) hidePop(); });
            $g.data('_datepicker',true);
        });
    };
})(jQuery);

// ===================== MULTISELECT =====================
(function($) {
    $.fn.multiselect = function(opts) {
        opts = opts || {};
        return this.each(function() {
            var $sel = $(this);
            if ($sel.data('_multiselect')) return;
            var isMul = $sel.prop('multiple');
            var bW = opts.buttonWidth || 'auto';
            var mH = opts.maxHeight || 200;
            var dUp = opts.dropUp || false;
            var selAll = opts.includeSelectAllOption || false;
            var nst = opts.nonSelectedText || 'None';
            var ast = opts.allSelectedText || 'All';
            var nd = opts.numberDisplayed || 3;
            $sel.hide();
            var $wrap = $('<div class="custom-multiselect"></div>');
            var $btn = $('<button type="button" class="ms-btn" style="width:'+bW+'"><span class="ms-text"></span> <span class="ms-caret"></span></button>');
            var $dd = $('<div class="ms-dropdown" style="max-height:'+mH+'px;width:'+bW+'"></div>');
            $wrap.append($btn);
            $('body').append($dd);
            $sel.after($wrap);
            $wrap.prepend($sel);
            function build() {
                $dd.empty();
                if (selAll && isMul) $dd.append('<div class="ms-item ms-select-all"><input type="checkbox"> Select All</div>');
                $sel.find('option').each(function(){
                    var $o=$(this), ck=$o.prop('selected')?' checked':'', tp=isMul?'checkbox':'radio';
                    $dd.append('<div class="ms-item" data-value="'+$o.val()+'"><input type="'+tp+'"'+ck+'> '+$o.text()+'</div>');
                });
            }
            function updText() {
                var s=$sel.find('option:selected'), txt;
                if(!s.length) txt=nst;
                else if(s.length===$sel.find('option').length&&isMul) txt=ast;
                else if(s.length>nd) txt=s.length+' selected';
                else txt=s.map(function(){return $(this).text();}).get().join(', ');
                $btn.find('.ms-text').text(txt);
            }
            function syncAll(){
                if(!selAll)return;
                var all=$dd.find('.ms-item:not(.ms-select-all) input:checked').length===$dd.find('.ms-item:not(.ms-select-all)').length;
                $dd.find('.ms-select-all input').prop('checked',all);
            }
            build(); updText();
            $btn.on('click',function(e){
                e.stopPropagation();
                var was=$dd.hasClass('show');
                $('.ms-dropdown.show').removeClass('show');
                if(was)return;
                var r=$btn[0].getBoundingClientRect();
                if(dUp) $dd.css({bottom:window.innerHeight-r.top+2,top:'auto',left:r.left});
                else $dd.css({top:r.bottom+2,bottom:'auto',left:r.left});
                $dd.addClass('show');
            });
            $dd.on('click','.ms-item:not(.ms-select-all)',function(e){
                e.stopPropagation();
                var $i=$(this),$c=$i.find('input');
                if(!$(e.target).is('input'))$c.prop('checked',!$c.prop('checked'));
                var v=$i.data('value');
                if(isMul){$sel.find('option[value="'+v+'"]').prop('selected',$c.prop('checked'));}
                else{$dd.find('.ms-item input').not($c).prop('checked',false);$sel.find('option').prop('selected',false);$sel.find('option[value="'+v+'"]').prop('selected',true);$dd.removeClass('show');}
                $sel.trigger('change'); updText(); syncAll();
            });
            $dd.on('click','.ms-select-all',function(e){
                e.stopPropagation();
                var $c=$(this).find('input');
                if(!$(e.target).is('input'))$c.prop('checked',!$c.prop('checked'));
                var ck=$c.prop('checked');
                $dd.find('.ms-item:not(.ms-select-all) input').prop('checked',ck);
                $sel.find('option').prop('selected',ck);
                $sel.trigger('change'); updText();
            });
            $(document).on('mousedown',function(e){ if(!$(e.target).closest($wrap).length && !$(e.target).closest($dd).length) $dd.removeClass('show'); });
            $sel.data('_multiselect',{rebuild:function(){build();updText();}});
        });
    };
})(jQuery);

// ===================== BOOTSTRAPDIALOG SHIM =====================
var BootstrapDialog = {
    TYPE_DANGER: 'danger',
    TYPE_INFO: 'info',
    TYPE_WARNING: 'warning',
    TYPE_SUCCESS: 'success',
    show: function(options) {
        var type = options.type || 'info';
        var title = options.title || '';
        var message = options.message || '';
        var onhide = options.onhide || null;
        var headerClass = 'text-bg-' + type;
        var id = 'bs-dialog-' + Date.now();
        var html = '<div class="modal" id="' + id + '" tabindex="-1">' +
            '<div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
            '<div class="modal-header ' + headerClass + '">' +
            '<h5 class="modal-title">' + title + '</h5>' +
            '<button type="button" class="btn-close btn-close-white" data-dismiss="modal"></button></div>' +
            '<div class="modal-body">' + message + '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>' +
            '</div></div></div></div>';
        $('body').append(html);
        var $modal = $('#' + id);
        $modal.on('hidden.modal', function() {
            $modal.remove();
            if (onhide) onhide();
        });
        $modal.modal('show');
    }
};

// ===================== APPLICATION =====================
var pathname = window.location.href.split("/")[0].split("?")[0];
var baseurl = pathname.concat("cmd/");
var mymap;
var marker;
var config;
var modalCallerIconElement;
var configShutter;
var assignRemoteAddress;
var unheardRemotesInterval = null;
var manualOperationInterval = null;

const buttonStop = 0x1;
const buttonUp = 0x2;
const buttonDown = 0x4;
const buttonProg = 0x8;

GetStartupInfo(true);
$(document).ready(function() {
    resizeDiv();
    setupListeners();
    injectIcons();
});

window.onresize = function(event) {
    resizeDiv();
}

function resizeDiv() {
    vph = $(window).height();
    $('#mymap').css({'height': vph*0.5 + 'px'});
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
               setupTableRemotes();
               if (config.Longitude == 0) {
                   $('#collapseOne').collapse('show');
               } else if (Object.keys(config.Shutters).length == 0){
                   $('.accordion-collapse.show').collapse('toggle');
                   $('#collapseTwo').collapse('show');
               }
               // Manual Operation is expanded by default (no shown.collapse
               // fires for content already open at load), so start polling
               // here once rather than only from the collapse event.
               if (manualOperationInterval === null && $('#collapseFour').hasClass('show')) {
                   manualOperationInterval = setInterval(refreshMovementStates, 3000);
               }
               $(".loader").removeClass("is-active");
            });
}

function setupMap(lat, lng) {
    mymap = L.map('mymap').setView([lat, lng], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(mymap);
	
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
      percentage = parseInt(evt['shutterAction'].substring(2));
      if (percentage > 0) {
         outstr += "for "+percentage+"% "
      } 
   } else if (evt['shutterAction'].substring(0, 4) == "down") {
      outstr += "lower ";
      percentage = parseInt(evt['shutterAction'].substring(4));
      if (percentage > 0) {
         outstr += "for "+percentage+"% "
      } 
   } else if (evt['shutterAction'].substring(0, 4) == "stop") {
      outstr += "stop (my) ";
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
                      marker.bindPopup("<center><b>An error occurred while saving.<br>Please try again</b></center>")
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

function addShutter(temp_id, name, duration) {
    var url = baseurl.concat("addShutter");
      $.post(  url,
               {name: name, duration: duration},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      $("#shutters tbody tr:last-child").attr('name', result.id);
                      sendCommand(result.id, "program", function() {$('#program-new-shutter').modal('show');})
                   } else {
                      setIcon(modalCallerIconElement[0], 'floppy');
                      $(modalCallerIconElement).removeClass("gly-spin");
        	      $(modalCallerIconElement).parents("tr").find(".save, .edit").toggle();
	              $(modalCallerIconElement).parents("tr").find(".delete").show();
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function editShutter(id, name, duration, resetIcon) {
    var url = baseurl.concat("editShutter");
      $.post(  url,
               {id: id, name: name, duration: duration},
               function(result, status){
                   resetIcon();
                   if ((status=="success") && (result.status == "OK")) {
                      if (result.nameChanged) {
                         BootstrapDialog.show({type: BootstrapDialog.TYPE_INFO, title: 'Information', message:'Please Note:<br>If you are using the Alexa (Echo Speaker) integration, please read the following carefully.<br><br>Alexa does not allow to automatically rename your device. To rename your device on Alexa, please delete your current device and then ask Alexa to discover new devices.'});
                      }
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

function pressButtons(id, buttons, longPress, confirmMessage) {
   var url = baseurl.concat("press");
   $.post(url,
      {shutter: id, buttons: buttons, longPress: longPress },
      function(result, status){
         if ((status=="success") && (result.status == "OK")) {
            if(confirmMessage != null) {
               BootstrapDialog.show({type: BootstrapDialog.TYPE_INFO, title: 'Information', message:confirmMessage});
            }
         } else {
            BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
         }
     }, "json");
}

function setIntermediatePosition(id, position) {
   var url = baseurl.concat("setIntermediatePosition");
   $.post(url,
      {shutter: id, position: position},
      function(result, status){
         if ((status=="success") && (result.status == "OK")) {
            config.ShutterIntermediatePositions[id] = result.intermediatePosition;
            updateManualOperationState();
            BootstrapDialog.show({type: BootstrapDialog.TYPE_INFO, title: 'Information', message:'My position saved.'});
         } else {
            BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message});
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
                   setIcon(modalCallerIconElement[0], 'floppy');
                   $(modalCallerIconElement).removeClass("gly-spin");
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

function assignRemote(address, shutterIds) {
    var url = baseurl.concat("assignRemote");
      $.post(  url,
               {address: address, "shutterIds[]": shutterIds},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      GetStartupInfo(false);
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}

function unassignRemote(address) {
    var url = baseurl.concat("unassignRemote");
      $.post(  url,
               {address: address},
               function(result, status){
                   if ((status=="success") && (result.status == "OK")) {
                      GetStartupInfo(false);
                   } else {
                      BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Received Error from Server: '+result.message, onhide: function(){GetStartupInfo(false);}});
                   }
               }, "json");
}



function setupTableShutters () {
    $("#shutters").find("tr:gt(0)").remove();
    $("#action_manual").empty();
    var shutterIds = Object.keys(config.Shutters);
    shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutter) {
        var row = '<tr name="'+shutter+'" rowtype="existing">' +
                     '<td name="name">'+config.Shutters[shutter]+'</td>' +
                     '<td name="duration">'+config.ShutterDurations[shutter]+'</td>' +
                     '<td class="td-action">' + $("#action_shutters").html() + '</td>' +
                  '</tr>';
        $("#shutters").append(row);

        var cell = '<div class="shutterRemote" name="'+shutter+'">' +
						'<div class="name">'+config.Shutters[shutter]+'</div>' +
                        '<div class="position"></div>' +
                        '<div class="state"></div>' +
                        '<div class="myPosition"></div>' +
                        '<a class="up btn" title="Up" data-toggle="tooltip" role="button"><svg viewBox="0 0 80 70" xmlns="http://www.w3.org/2000/svg"><path d="M35 14 Q40 0, 45 14 C55 30, 67 52, 71 60 Q75 68, 64 68 L16 68 Q5 68, 9 60 C13 52, 25 30, 35 14 Z" fill="#ccc" stroke="#aaa" stroke-width="1.5"/></svg></a>' +
                        '<a class="stop btn" title="Stop" data-toggle="tooltip" role="button"><svg viewBox="0 0 90 40" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="86" height="36" rx="18" fill="#ccc" stroke="#aaa" stroke-width="1.5"/></svg></a>' +
                        '<a class="down btn" title="Down" data-toggle="tooltip" role="button"><svg viewBox="0 0 80 70" xmlns="http://www.w3.org/2000/svg"><path d="M9 10 Q5 2, 16 2 L64 2 Q75 2, 71 10 C67 18, 55 40, 45 56 Q40 70, 35 56 C25 40, 13 18, 9 10 Z" fill="#ccc" stroke="#aaa" stroke-width="1.5"/></svg></a>' +
                  '</div>';
        $("#action_manual").append(cell);
    });

    $("#shuttersCount").text($("#shutters").find('tr').length-1);
    updateManualOperationState();
}

// Reflects config.MovementStates ('opening'/'closing'/'stopped'/null),
// config.Positions (0-100), and config.ShutterIntermediatePositions (the
// stored "My" position, 0-100 or null if unset) onto each Manual Operation
// card — kept current by refreshMovementStates(), polled while that section
// is visible, so a physical remote press (or a command from elsewhere)
// shows up here too, not just commands sent from this page.
function updateManualOperationState() {
    if (!config.MovementStates || !config.Positions) { return; }
    Object.keys(config.MovementStates).forEach(function(shutter) {
        var state = config.MovementStates[shutter];
        var card = $('.shutterRemote[name="'+shutter+'"]');
        var label = (state == "opening") ? "Opening..." : (state == "closing") ? "Closing..." : "";
        card.find(".state").text(label);
        card.find(".position").text(config.Positions[shutter] + "%");
        card.toggleClass("moving", state == "opening" || state == "closing");
        var myPosition = config.ShutterIntermediatePositions ? config.ShutterIntermediatePositions[shutter] : null;
        var myPositionUnset = (myPosition === null || myPosition === undefined);
        card.find(".myPosition").text(myPositionUnset ? "⚠ My position not set" : "My: " + myPosition + "%")
            .toggleClass("unset", myPositionUnset);
    });
}

function refreshMovementStates() {
    $.getJSON(baseurl.concat("getConfig"), {}, function(result, status){
        if (!(status=="success")) { return; }
        config.MovementStates = result.MovementStates;
        config.Positions = result.Positions;
        config.ShutterIntermediatePositions = result.ShutterIntermediatePositions;
        updateManualOperationState();
    });
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
              $(item).parent().addClass('selected');
           }
        }
        if (evt['shutterAction'].substring(0, 2) == "up") {
           thisRow.find('#scheduleEdit .shutterActionUp').removeClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionStop').addClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionDown').addClass("inactiveDirection");
           percentage = parseInt(evt['shutterAction'].substring(2));
           if (percentage > 0) {
              if (percentage < 10) {percentage = 10}
              else if (percentage < 20) {percentage = 20}
              else if (percentage < 25) {percentage = 25}
              else if (percentage < 30) {percentage = 30}
              thisRow.find('.durationList').val(percentage)
           } else {
              thisRow.find('.durationList').val(0)           
           }
        } else if (evt['shutterAction'].substring(0, 4) == "down") {
           thisRow.find('#scheduleEdit .shutterActionDown').removeClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionStop').addClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionUp').addClass("inactiveDirection");
           percentage = parseInt(evt['shutterAction'].substring(4));
           if (percentage > 0) {
              if (percentage < 10) {percentage = 10}
              else if (percentage < 20) {percentage = 20}
              else if (percentage < 25) {percentage = 25}
              else if (percentage < 30) {percentage = 30}
              thisRow.find('.durationList').val(percentage)
           } else {
              thisRow.find('.durationList').val(0)           
           }
        } else if (evt['shutterAction'].substring(0, 4) == "stop") {
           thisRow.find('#scheduleEdit .shutterActionDown').addClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionStop').removeClass("inactiveDirection");
           thisRow.find('#scheduleEdit .shutterActionUp').addClass("inactiveDirection");
           thisRow.find('.durationList').val(0)
        }

        shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutter) {
           thisRow.find('.shuttersList').append('<option value="'+shutter+'"'+(evt['shutterIds'].includes(shutter) ? " selected" : "") +'>'+config.Shutters[shutter]+'</option>');
        });
        
    });
    $("#scheduleCount").text($("#schedule").find('tr').length-1);

    // Ensure all scheduleEdit divs are visible so plugins initialize with correct dimensions
    $('[rowtype="existing"] .editbox').show();

    // Initialize plugins
    initTooltips();
    $('[rowtype="existing"] input[type=checkbox][data-toggle^=toggle]').bootstrapToggle();

    $('[rowtype="existing"] .clockDelay').bootstrapSlider();
    $('[rowtype="existing"] .clockDelay').on("slide", function(slideEvt) {$(this).parent().find("#clockDelayVal").val(slideEvt.value)});
    $('[rowtype="existing"] .clockpicker').clockpicker({placement: 'top', align: 'left', donetext: 'Done', autoclose: true});

    $('[rowtype="existing"] .date').datepicker({placement: 'top', autoclose: true, format: "yyyy/mm/dd"});    
    $('[rowtype="existing"] .weekDays-selector :checkbox').change(function() { if (this.checked) { $(this).parent().addClass('selected') } else { $(this).parent().removeClass('selected')}});
    
    $('[rowtype="existing"] .durationList').multiselect({dropUp: true, maxHeight: 320, buttonWidth: '75px', buttonClass: 'btn btn-secondary'});
    $('[rowtype="existing"] .shuttersList').multiselect({dropUp: true, maxHeight: 200, includeSelectAllOption: true, buttonWidth: '130px', nonSelectedText: 'None', allSelectedText: 'All', numberDisplayed: 1, nSelectedText: 'Selected', buttonClass: 'btn btn-secondary'});

    // Hide/show editboxes after plugin initialization
    $('.editbox').hide();
    $('.editbox.in').show();
}

function setupTableRemotes () {
    $("#remotes").find("tr:gt(0)").remove();
    var addresses = Object.keys(config.PhysicalRemotes);
    addresses.sort().forEach(function(address) {
        var shutterNames = config.PhysicalRemotes[address].map(function(shutterId) {
            return config.Shutters[shutterId] || shutterId;
        }).join(", ");
        var row = '<tr name="'+address+'" rowtype="existing">' +
                     '<td name="address">'+address+'</td>' +
                     '<td name="shutters">'+shutterNames+'</td>' +
                     '<td class="td-action">' + $("#action_remotes").html() + '</td>' +
                  '</tr>';
        $("#remotes").append(row);
    });
    $("#remotesCount").text($("#remotes").find('tr').length-1);
    initTooltips();
}

// Polled only while the "Physical Remotes" section is expanded (started/
// stopped by the shown.collapse/hidden.collapse handlers in setupListeners).
function refreshUnheardRemotes() {
    var url = baseurl.concat("getUnheardRemotes");
    $.getJSON(url, {}, function(result, status){
        if (!(status=="success") || result.status != "OK") { return; }
        $("#unheardRemotes").find("tr:gt(0)").remove();
        var pairedAddresses = Object.keys(config.PhysicalRemotes);
        result.remotes.forEach(function(remote) {
            if (pairedAddresses.includes(remote.address)) { return; } // paired since last poll
            var row = '<tr name="'+remote.address+'" rowtype="existing">' +
                         '<td name="address">'+remote.address+'</td>' +
                         '<td name="button">'+remote.buttonName+'</td>' +
                         '<td class="td-action">' + $("#action_unheard_remotes").html() + '</td>' +
                      '</tr>';
            $("#unheardRemotes").append(row);
        });
        initTooltips();
    });
}

function openAssignRemoteModal(address, currentShutterIds) {
    assignRemoteAddress = address;
    $("#assign-remote-address").text(address);
    var select = $("#assignRemoteShutters");
    if (select.data('multiselect')) {
        select.multiselect('destroy');
    }
    select.empty();
    var shutterIds = Object.keys(config.Shutters);
    shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutterId) {
        var selected = currentShutterIds.includes(shutterId) ? " selected" : "";
        select.append('<option value="'+shutterId+'"'+selected+'>'+config.Shutters[shutterId]+'</option>');
    });
    select.multiselect({dropUp: true, maxHeight: 200, includeSelectAllOption: true, buttonWidth: '130px', nonSelectedText: 'None', allSelectedText: 'All', numberDisplayed: 1, nSelectedText: 'Selected', buttonClass: 'btn btn-secondary'});
    $('#assign-remote').modal('show');
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

    initTooltips();

    // Append table with add row form on add new button click
    $(".addShutters").click(function(){
	$(this).attr("disabled", "disabled");
        var index = $("#shutters tbody tr:last-child").index();
        var row = '<tr name="newkey_'+index+'" rowtype="new">' +
                      '<td name="name"><input type="text" class="form-control"></td>' +
                      '<td name="duration"><input type="text" class="form-control"></td>' +
   		      '<td class="td-action">' + $("#action_shutters").html() + '</td>' +
                  '</tr>';
    	$("#shutters").append(row);		

	$('#shutters tbody tr').eq(index + 1).find('.save, .edit').toggle();
        initTooltips();
    });

    // Append table with add row form on add new button click
    $(".addSchedule").click(function(){
	$(this).attr("disabled", "disabled");
        var index = $("#schedule tbody tr:last-child").index();
        var row = '<tr name="newkey_'+index+'" rowtype="new">'+
                      '<td name="name">' + $("#description_schedule").html().replace("TEXT_0", "new schedule") + '</td>' +
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
        thisRow.find('.weekDays-selector :checkbox').change(function() { if (this.checked) { $(this).parent().addClass('selected') } else { $(this).parent().removeClass('selected')}});
        var shutterIds = Object.keys(config.Shutters);
        shutterIds.sort(function(a, b) { return config.Shutters[a].toLowerCase() > config.Shutters[b].toLowerCase()}).forEach(function(shutter) {
           thisRow.find('.shuttersList').append('<option value="'+shutter+'">'+config.Shutters[shutter]+'</option>');
        });
        thisRow.find('.durationList').val(0);
        thisRow.find('.durationList').multiselect({dropUp: true, maxHeight: 320, buttonWidth: '75px', buttonClass: 'btn btn-secondary'});
        thisRow.find('.shuttersList').multiselect({dropUp: true, maxHeight: 200, includeSelectAllOption: true, buttonWidth: '130px', nonSelectedText: 'None', allSelectedText: 'All', numberDisplayed: 1, nSelectedText: 'Selected', buttonClass: 'btn btn-secondary'});

	$('#schedule tbody tr').eq(index + 1).find('.save, .edit').toggle();
        initTooltips();
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
              modalCallerIconElement = $(this).find(".icon");
              setIcon(modalCallerIconElement[0], 'arrow-clockwise');
              $(modalCallerIconElement).addClass("gly-spin");
              addShutter(mydata.id, mydata.name, mydata.duration);
           } else if (mytype == "AMEND") { 
              var iconElement = $(this).find(".icon");
              setIcon(iconElement[0], 'arrow-clockwise');
              $(iconElement).addClass("gly-spin");
              editShutter(mydata.id, mydata.name, mydata.duration, function(){
                 setIcon(iconElement[0], 'floppy');
                 $(iconElement).removeClass("gly-spin");
    	         $(iconElement).parents("tr").find(".save, .edit").toggle();
	         $(iconElement).parents("tr").find(".delete").show();
              });
           }
           
	}		
    });

    // Add row on add button click
    $(document).on("click", ".saveSchedule", function(){
	removeOrphanedTooltips();
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
           shutterIdsField.closest('.custom-multiselect').find('.ms-btn').addClass("error");
           empty = true;
        } else {
           shutterIdsField.closest('.custom-multiselect').find('.ms-btn').removeClass("error");
        }
        $(this).parents("tr").find(".error").first().focus();

        durationField = thisRow.find('#scheduleEdit .durationList');
        if (durationField.val().length == 0) {
           durationField.closest('.custom-multiselect').find('.ms-btn').addClass("error");
           empty = true;
        } else {
           durationField.closest('.custom-multiselect').find('.ms-btn').removeClass("error");
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
              modalCallerIconElement = $(this).find(".icon");
              setIcon(modalCallerIconElement[0], 'arrow-clockwise');
              $(modalCallerIconElement).addClass("gly-spin");
              addSchedule(mydata.id, mydata);
           } else if (mytype == "AMEND") { 
              var iconElement = $(this).find(".icon");
              setIcon(iconElement[0], 'arrow-clockwise');
              $(iconElement).addClass("gly-spin");
              editSchedule(mydata.id, mydata, function(){
                 config.Schedule[mydata.id] = mydata;
                 evt = config.Schedule[mydata.id];
                 $(iconElement).parents("tr").find('#scheduleText').html(prettyPrintSchedule(evt, config.Shutters));
                 $(iconElement).parents("tr").find(".editbox").toggle();              
                 setIcon(iconElement[0], 'floppy');
                 $(iconElement).removeClass("gly-spin");
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

    $(document).on('click', ".shutterActionUp", function() {
         $(this).parent().find('.shutterActionUp').removeClass("inactiveDirection");
         $(this).parent().find('.shutterActionStop').addClass("inactiveDirection");
         $(this).parent().find('.shutterActionDown').addClass("inactiveDirection");
    });

    $(document).on('click', ".shutterActionStop", function() {
         $(this).parent().find('.shutterActionUp').addClass("inactiveDirection");
         $(this).parent().find('.shutterActionStop').removeClass("inactiveDirection");
         $(this).parent().find('.shutterActionDown').addClass("inactiveDirection");
    });

    $(document).on('click', ".shutterActionDown", function() {
         $(this).parent().find('.shutterActionUp').addClass("inactiveDirection");
         $(this).parent().find('.shutterActionStop').addClass("inactiveDirection");
         $(this).parent().find('.shutterActionDown').removeClass("inactiveDirection");
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

    // Edit row on configure button click
    $(document).on("click", ".configureShutters", function(){
       configShutter = $(this).parents("tr").attr('name');
       var current = config.ShutterIntermediatePositions[configShutter];
       $('#intermediatePositionInput').val((current === null || current === undefined) ? "" : current);
       $('#configure-shutter').modal('show');
    });

    // Reassign an already-paired remote
    $(document).on("click", ".editRemote", function(){
       var address = $(this).parents("tr").attr('name');
       openAssignRemoteModal(address, config.PhysicalRemotes[address] || []);
    });

    // Assign a remote heard under "Recently Heard"
    $(document).on("click", ".assignRemoteBtn", function(){
       var address = $(this).parents("tr").attr('name');
       openAssignRemoteModal(address, []);
    });

    $('#assign-remote-save').on("click", function(){
        var shutterIds = $("#assignRemoteShutters").val() || [];
        if (shutterIds.length == 0) {
            BootstrapDialog.show({type: BootstrapDialog.TYPE_DANGER, title: 'Error', message:'Select at least one shutter.'});
            return;
        }
        assignRemote(assignRemoteAddress, shutterIds);
        $('#assign-remote').modal('hide');
    });

    // Edit row on edit button click
    $(document).on("click", ".editSchedule", function(){		
        $(this).parents("tr").find('.editbox').toggle();
	$(this).parents("tr").find(".save, .edit, .delete").toggle();
	$(".addSchedule").attr("disabled", "disabled");
    });


    $(document).on("click", ".delete", function(){		
        modalCallerIconElement = $(this).find(".icon");
        setIcon(modalCallerIconElement[0], 'arrow-clockwise');
        $(modalCallerIconElement).addClass("gly-spin");
    });

    
    $('#confirm-delete').on('hide.modal', function(e) {
        setIcon(modalCallerIconElement[0], 'trash');
        $(modalCallerIconElement).removeClass("gly-spin");
    }); 
    
    $('#confirm-delete-ok').on("click", function(){
        var tableId = $(modalCallerIconElement).parents("table").attr('id');
        if ($(modalCallerIconElement).parents("tr").find('.edit').is(":visible")) {
             var rowId = $(modalCallerIconElement).parents("tr").attr('name');
             if (tableId == "shutters") {
                 deleteShutter(rowId);
             } else if (tableId == "schedule") {
                 deleteSchedule(rowId);
             } else if (tableId == "remotes") {
                 unassignRemote(rowId);
             }
        }
        $('#confirm-delete').modal('hide');
        $("#"+tableId+"Count").text($("#"+tableId).find('tr').length-2);
        $(modalCallerIconElement).parents("tr").remove();
        $(".addSchedule, .addShutters").removeAttr("disabled");
    });


    $('#program-new-shutter').on('hide.modal', function(e) {
        setIcon(modalCallerIconElement[0], 'floppy');
        $(modalCallerIconElement).removeClass("gly-spin");
        $(modalCallerIconElement).parents("tr").find(".save, .edit").toggle();
	$(modalCallerIconElement).parents("tr").find(".delete").show();
        GetStartupInfo(false);
    });
    
    $('#collapseOne').on('shown.collapse', function () {
        resizeDiv();
        if (mymap == undefined) {
            setupMap(config.Latitude, config.Longitude);
        } else {
            mymap.invalidateSize();
        }
    })

    $('#collapseFour').on('shown.collapse', function () {
        if (manualOperationInterval === null) {
            refreshMovementStates();
            manualOperationInterval = setInterval(refreshMovementStates, 3000);
        }
    })

    $('#collapseFour').on('hidden.collapse', function () {
        clearInterval(manualOperationInterval);
        manualOperationInterval = null;
    })

    $('#collapseFive').on('shown.collapse', function () {
        refreshUnheardRemotes();
        unheardRemotesInterval = setInterval(refreshUnheardRemotes, 3000);
    })

    $('#collapseFive').on('hidden.collapse', function () {
        clearInterval(unheardRemotesInterval);
    })

    $('#program-new-shutter-ok').on("click", function(){
        //  We are good, the hide.modal event will take care of refreshing the main window
    });
    $('#program-new-shutter-try').on("click", function(){
        //  Try to program again
        $('#program-new-shutter-try').text("Sending..")
        sendCommand($("#shutters tbody tr:last-child").attr('name'), "program", function() {$('#program-new-shutter-try').text("Try Programming again")})
    });
    
    $('#program-new-shutter-abort').on("click", function(){
        // Abort, delete the new shutter
        deleteShutter($("#shutters tbody tr:last-child").attr('name'));
        $('#program-new-shutter').modal('hide');
        // The hide.modal event will take care of refreshing the main window
    });

    $(document).on("click", '.press-button-up-short', function(){
        pressButtons(configShutter, buttonUp, false);
    });

    $(document).on("click", '.press-button-down-short', function(){
        pressButtons(configShutter, buttonDown, false);
    });
    
    $(document).on("click", '.press-button-stop-short', function(){
        pressButtons(configShutter, buttonStop, false);
    });

    $(document).on("click", '.press-button-up-down-long', function(){
        pressButtons(configShutter, buttonUp | buttonDown, true, "The blind should have jogged. If not, try again.");
    });

    $(document).on("click", '.press-button-up-stop-short', function(){
     pressButtons(configShutter, buttonUp | buttonStop, false, "The blind should have started moving up. If not, try again.");
    });

    $(document).on("click", '.press-button-down-stop-short', function(){
     pressButtons(configShutter, buttonDown | buttonStop, false, "The blind should have started moving down. If not, try again.");
    });

    $(document).on("click", '.press-button-stop-long', function(){
     pressButtons(configShutter, buttonStop, true, "The blind should have jogged. If not, try again.");
  });

  $(document).on("click", '.press-button-prog-long', function(){
     pressButtons(configShutter, buttonProg, true);
  });

  $('#save-intermediate-position').on("click", function(){
     setIntermediatePosition(configShutter, $('#intermediatePositionInput').val());
  });

  $('#clear-intermediate-position').on("click", function(){
     $('#intermediatePositionInput').val("");
     setIntermediatePosition(configShutter, "");
  });


    // Shutter Commands
    $(document).on("click", ".up", function(){		
        var key = $(this).parents("div").attr('name');
        var iconElement = $(this).find("svg");
        $(iconElement).toggleClass("button_transparent");
        sendCommand(key, "up", function(){$(iconElement).toggleClass("button_transparent")});
    });
    $(document).on("click", ".down", function(){		
        var key = $(this).parents("div").attr('name');
        var iconElement = $(this).find("svg");
        $(iconElement).toggleClass("button_transparent");
        sendCommand(key, "down", function(){$(iconElement).toggleClass("button_transparent")});
    });
    $(document).on("click", ".stop", function(){		
        var key = $(this).parents("div").attr('name');
        var iconElement = $(this).find("svg");
        $(iconElement).toggleClass("button_transparent");
        sendCommand(key, "stop", function(){$(iconElement).toggleClass("button_transparent")});
    });

}