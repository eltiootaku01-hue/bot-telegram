const CATALOG_URL = new URL("../data/cards_equipment.json", import.meta.url);

const REQUIRED_CARD_FIELDS = [
  "card_id",
  "name",
  "character_owner",
  "card_type",
  "rarity",
  "cost",
  "frame_color",
  "art_image_url",
  "description",
  "gameplay_effects",
  "3d_attachment",
];

const REQUIRED_ATTACHMENT_FIELDS = [
  "model_url",
  "target_bone",
  "socket_name",
  "offset_position",
  "offset_rotation",
  "scale",
];

function assertVector(value, fieldName) {
  if (
    !Array.isArray(value)
    || value.length !== 3
    || value.some((entry) => typeof entry !== "number" || !Number.isFinite(entry))
  ) {
    throw new TypeError(`${fieldName} debe ser un vector numérico [x, y, z].`);
  }
}

function validateCard(card, index) {
  if (!card || typeof card !== "object" || Array.isArray(card)) {
    throw new TypeError(`equipment_cards[${index}] debe ser un objeto.`);
  }

  for (const field of REQUIRED_CARD_FIELDS) {
    if (!(field in card)) {
      throw new TypeError(`equipment_cards[${index}] no contiene '${field}'.`);
    }
  }

  if (
    typeof card.card_id !== "string"
    || !/^[a-z0-9][a-z0-9_-]*$/i.test(card.card_id)
  ) {
    throw new TypeError(`equipment_cards[${index}].card_id no es válido.`);
  }

  if (card.card_type !== "EQUIPO") {
    throw new TypeError(`La carta ${card.card_id} no es de tipo EQUIPO.`);
  }

  if (typeof card.cost !== "number" || !Number.isInteger(card.cost) || card.cost < 0) {
    throw new TypeError(`La carta ${card.card_id} tiene un coste inválido.`);
  }

  if (
    typeof card.frame_color !== "string"
    || !/^#[0-9a-f]{6}$/i.test(card.frame_color)
  ) {
    throw new TypeError(`La carta ${card.card_id} tiene un frame_color inválido.`);
  }

  if (
    typeof card.gameplay_effects !== "object"
    || card.gameplay_effects === null
    || Array.isArray(card.gameplay_effects)
  ) {
    throw new TypeError(`La carta ${card.card_id} tiene gameplay_effects inválido.`);
  }

  const attachment = card["3d_attachment"];
  if (!attachment || typeof attachment !== "object" || Array.isArray(attachment)) {
    throw new TypeError(`La carta ${card.card_id} no tiene 3d_attachment válido.`);
  }

  for (const field of REQUIRED_ATTACHMENT_FIELDS) {
    if (!(field in attachment)) {
      throw new TypeError(`La carta ${card.card_id} no contiene 3d_attachment.${field}.`);
    }
  }

  for (const field of ["model_url", "target_bone", "socket_name"]) {
    if (typeof attachment[field] !== "string" || !attachment[field].trim()) {
      throw new TypeError(`La carta ${card.card_id} tiene 3d_attachment.${field} inválido.`);
    }
  }

  assertVector(attachment.offset_position, `La carta ${card.card_id}.offset_position`);
  assertVector(attachment.offset_rotation, `La carta ${card.card_id}.offset_rotation`);
  assertVector(attachment.scale, `La carta ${card.card_id}.scale`);

  if (attachment.scale.some((entry) => entry <= 0)) {
    throw new RangeError(`La carta ${card.card_id} debe tener una escala positiva.`);
  }

  return card;
}

/**
 * Carga y valida el catálogo de equipamiento desde la misma raíz de la WebApp.
 *
 * @returns {Promise<ReadonlyArray<object>>}
 */
export async function loadEquipmentCatalog() {
  const response = await fetch(CATALOG_URL, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `No se pudo cargar el catálogo de equipamiento: HTTP ${response.status}.`,
    );
  }

  const data = await response.json();

  if (!data || typeof data !== "object" || !Array.isArray(data.equipment_cards)) {
    throw new TypeError("El catálogo no contiene equipment_cards.");
  }

  if (typeof data.catalog_version !== "string" || !data.catalog_version.trim()) {
    throw new TypeError("El catálogo no contiene catalog_version.");
  }

  const seen = new Set();
  const cards = data.equipment_cards.map((card, index) => {
    const validated = validateCard(card, index);
    if (seen.has(validated.card_id)) {
      throw new TypeError(`card_id duplicado: ${validated.card_id}.`);
    }
    seen.add(validated.card_id);
    return Object.freeze({
      ...validated,
      gameplay_effects: Object.freeze({ ...validated.gameplay_effects }),
      "3d_attachment": Object.freeze({
        ...validated["3d_attachment"],
        offset_position: Object.freeze([...validated["3d_attachment"].offset_position]),
        offset_rotation: Object.freeze([...validated["3d_attachment"].offset_rotation]),
        scale: Object.freeze([...validated["3d_attachment"].scale]),
      }),
    });
  });

  return Object.freeze(cards);
}

export function findEquipmentCard(cards, cardId) {
  if (!Array.isArray(cards)) {
    throw new TypeError("cards debe ser un array.");
  }
  return cards.find((card) => card.card_id === cardId) || null;
}

export function equipmentCardToAttachmentConfig(card) {
  if (!card || typeof card !== "object") {
    throw new TypeError("card es obligatorio.");
  }

  const attachment = card["3d_attachment"];
  if (!attachment) {
    throw new TypeError(`La carta ${card.card_id || "desconocida"} no tiene montaje 3D.`);
  }

  return {
    cardId: card.card_id,
    modelUrl: new URL(attachment.model_url, document.baseURI).href,
    targetBone: attachment.target_bone,
    socketName: attachment.socket_name,
    offsetPos: [...attachment.offset_position],
    offsetRot: [...attachment.offset_rotation],
    scale: [...attachment.scale],
  };
}

export function formatEquipmentEffects(effects) {
  return Object.entries(effects || {})
    .map(([key, value]) => `${key}: ${typeof value === "number" ? value : String(value)}`)
    .join(" · ");
}

export function equipmentAssetUrl(path) {
  if (typeof path !== "string" || !path.trim()) {
    throw new TypeError("path de asset inválido.");
  }
  return new URL(path, document.baseURI).href;
}
