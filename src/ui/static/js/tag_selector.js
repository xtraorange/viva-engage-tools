(function (window) {
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function parseCsvTags(value) {
    return String(value || '')
      .split(',')
      .map(function (tag) { return tag.trim(); })
      .filter(Boolean);
  }

  function uniqueTags(values) {
    var seen = new Set();
    var output = [];
    (values || []).forEach(function (raw) {
      var tag = String(raw || '').trim();
      if (!tag) return;
      var key = tag.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      output.push(tag);
    });
    return output;
  }

  function createTagSelector(options) {
    var hidden = document.getElementById(options.hiddenInputId);
    var input = document.getElementById(options.inputId);
    var suggestions = document.getElementById(options.suggestionsId);
    var chipContainer = document.getElementById(options.chipContainerId);
    var addButton = options.addButtonId ? document.getElementById(options.addButtonId) : null;
    var allTags = Array.isArray(options.allTags) ? options.allTags : [];

    if (!hidden || !input || !suggestions || !chipContainer) {
      return null;
    }

    var state = {
      tags: uniqueTags(parseCsvTags(hidden.value)),
    };

    function notifyChange() {
      hidden.value = state.tags.join(', ');
      if (typeof options.onChange === 'function') {
        options.onChange(state.tags.slice());
      }
    }

    function defaultChipRenderer(tag, index) {
      return '<span class="badge bg-primary d-inline-flex align-items-center gap-1">'
        + escapeHtml(tag)
        + '<button type="button" class="btn-close btn-close-white" aria-label="Remove ' + escapeHtml(tag) + '" data-tag-index="' + index + '"></button>'
        + '</span>';
    }

    function renderChips() {
      var renderer = typeof options.renderChip === 'function' ? options.renderChip : defaultChipRenderer;
      chipContainer.innerHTML = state.tags.map(function (tag, index) {
        return renderer(tag, index, escapeHtml);
      }).join('');
      notifyChange();
    }

    function addTag(rawTag) {
      var tag = String(rawTag || '').trim();
      if (!tag) return;
      var exists = state.tags.some(function (existing) {
        return existing.toLowerCase() === tag.toLowerCase();
      });
      if (exists) return;
      state.tags.push(tag);
      renderChips();
    }

    function removeTag(index) {
      if (!Number.isInteger(index) || index < 0 || index >= state.tags.length) return;
      state.tags.splice(index, 1);
      renderChips();
    }

    function hideSuggestions() {
      suggestions.style.display = 'none';
    }

    function renderSuggestions(query) {
      var normalized = String(query || '').trim().toLowerCase();
      if (!normalized) {
        hideSuggestions();
        return;
      }

      var matches = allTags
        .filter(function (tag) {
          var alreadyAdded = state.tags.some(function (existing) {
            return existing.toLowerCase() === String(tag).toLowerCase();
          });
          return !alreadyAdded && String(tag).toLowerCase().includes(normalized);
        })
        .slice(0, 10);

      if (matches.length === 0) {
        suggestions.innerHTML = '<div class="list-group-item text-muted">Press Enter to add this tag</div>';
      } else {
        suggestions.innerHTML = matches.map(function (tag) {
          return '<a href="#" class="list-group-item list-group-item-action" data-tag="' + escapeHtml(tag) + '">' + escapeHtml(tag) + '</a>';
        }).join('');

        suggestions.querySelectorAll('a').forEach(function (item) {
          item.addEventListener('click', function (event) {
            event.preventDefault();
            addTag(item.getAttribute('data-tag'));
            input.value = '';
            hideSuggestions();
            input.focus();
          });
        });
      }

      suggestions.style.display = 'block';
    }

    function submitInputTag() {
      addTag(input.value);
      input.value = '';
      hideSuggestions();
      input.focus();
    }

    if (addButton) {
      addButton.addEventListener('click', submitInputTag);
    }

    input.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      submitInputTag();
    });

    input.addEventListener('input', function (event) {
      renderSuggestions(event.target.value);
    });

    input.addEventListener('blur', function () {
      setTimeout(hideSuggestions, 150);
    });

    chipContainer.addEventListener('click', function (event) {
      var button = event.target.closest('button[data-tag-index]');
      if (!button) return;
      removeTag(Number(button.getAttribute('data-tag-index')));
    });

    renderChips();

    return {
      addTag: addTag,
      getTags: function () { return state.tags.slice(); },
      setTags: function (values) {
        state.tags = uniqueTags(Array.isArray(values) ? values : parseCsvTags(values));
        renderChips();
      },
      hideSuggestions: hideSuggestions,
      parseCsvTags: parseCsvTags,
    };
  }

  window.TagSelector = {
    create: createTagSelector,
    parseCsvTags: parseCsvTags,
    escapeHtml: escapeHtml,
  };
}(window));
