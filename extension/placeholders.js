/*
 * A control's own "Choose one" row, recognised the same way everywhere.
 *
 * There were three copies of this: one in the service, one in the injected
 * verifier, and one in the panel. Two of them were kept up to date and the
 * panel's was not, so a select whose only row was "— Make a Selection —"
 * offered that row to the applicant as an answer to pick. Pressing it did
 * nothing, because it is not an answer -- it is the control asking.
 *
 * The panel's copy also tested the label as written. The em dashes a form
 * decorates with are not part of the word, so "— Make a Selection —" was not
 * "make a selection" and matched nothing at all.
 *
 * This file has no dependencies so that both the panel and the page can load
 * it, and there is one list rather than three.
 */
(function (root) {
  "use strict";

  const PLACEHOLDER =
    /^(|-+|\.+|_+|no selection|none selected|nothing selected|not selected|select\b.*|please select.*|make a selection.*|select one.*|choose\b.*|pick one|--.*--|\(.*\)|click to select.*|type to search.*|start typing.*|please enter.*|enter \d+ or more.*|no results.*|no matches.*|loading.*|searching.*|search\.\.\.|n\/?a|tbd|optional|required)$/i;

  //: Every dash a form might draw, and the marks it decorates with. None of
  //: them are part of what the row says.
  const DASHES = /[‐-―−]/g;
  const MARKS = /[*†‡•✱✲✳✻✽⁎∗＊★☆]/g;
  const EDGES = /^[\s\-_.:,]+|[\s\-_.:,]+$/g;

  /** A row's text with the decoration taken off. */
  function plain(text) {
    return String(text === null || text === undefined ? "" : text)
      .replace(DASHES, "-")
      .replace(MARKS, " ")
      .toLowerCase()
      .replace(EDGES, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function looksLikePlaceholder(text) {
    return PLACEHOLDER.test(plain(text));
  }

  root.ApplyPilotPlaceholders = {
    looksLikePlaceholder: looksLikePlaceholder,
    plain: plain,
    PLACEHOLDER: PLACEHOLDER,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
