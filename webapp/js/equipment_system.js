/**
 * Sistema de equipamiento táctico TCG para modelos Three.js.
 *
 * Requiere que THREE y THREE.GLTFLoader estén disponibles antes de importar
 * este módulo. El demo web los carga desde CDN.
 */
export class EquipmentSystem {
  constructor(scene, loader = null) {
    if (!scene) {
      throw new TypeError("EquipmentSystem requiere una escena Three.js.");
    }

    const THREE_NS = globalThis.THREE;
    if (!THREE_NS) {
      throw new Error("Three.js no está cargado.");
    }

    if (!loader && !THREE_NS.GLTFLoader) {
      throw new Error("GLTFLoader no está cargado.");
    }

    this.scene = scene;
    this.loader = loader || new THREE_NS.GLTFLoader();
    this.equippedItems = new Map();
    this.bonesMap = new Map();
    this.characterModel = null;
    this.pendingLoads = new Map();
  }

  /**
   * Indexa todos los huesos del modelo para búsquedas rápidas.
   * @param {THREE.Object3D} characterModel
   */
  initCharacterBones(characterModel) {
    if (!characterModel || typeof characterModel.traverse !== "function") {
      throw new TypeError("characterModel debe ser un THREE.Object3D válido.");
    }

    this.characterModel = characterModel;
    this.bonesMap.clear();

    characterModel.traverse((object) => {
      if (object && object.isBone && object.name) {
        this.bonesMap.set(object.name.toLowerCase(), object);
      }
    });

    console.info(
      `[EQUIPMENT SYSTEM] Esqueleto indexado: ${this.bonesMap.size} huesos encontrados.`
    );

    return this.bonesMap.size;
  }

  /**
   * Acopla un accesorio GLTF/GLB a un hueso.
   *
   * La carga es asíncrona. Si el jugador desequipa la carta antes de que termine
   * la carga, el asset cargado se libera y no vuelve a aparecer.
   *
   * @param {Object} config
   * @returns {Promise<THREE.Object3D>}
   */
  attachEquipment(config) {
    this.#validateConfig(config);

    const {
      cardId,
      modelUrl,
      targetBone,
      offsetPos = [0, 0, 0],
      offsetRot = [0, 0, 0],
      scale = [1, 1, 1],
    } = config;

    if (this.equippedItems.has(cardId)) {
      this.detachEquipment(cardId);
    }

    const parentObject = this.findBone(targetBone) || this.characterModel;
    if (!parentObject) {
      return Promise.reject(
        new Error("No existe un modelo de personaje donde montar el equipamiento.")
      );
    }

    const loadToken = Symbol(cardId);
    this.pendingLoads.set(cardId, loadToken);

    return new Promise((resolve, reject) => {
      this.loader.load(
        modelUrl,
        (gltf) => {
          const activeToken = this.pendingLoads.get(cardId);
          if (activeToken !== loadToken) {
            this.#disposeObject(gltf.scene);
            reject(new Error("Carga de equipamiento cancelada o reemplazada."));
            return;
          }

          this.pendingLoads.delete(cardId);

          const accessoryMesh = gltf.scene;
          accessoryMesh.position.set(...offsetPos);
          accessoryMesh.rotation.set(...offsetRot);
          accessoryMesh.scale.set(...scale);

          parentObject.add(accessoryMesh);

          this.equippedItems.set(cardId, {
            mesh: accessoryMesh,
            parent: parentObject,
            modelUrl,
            targetBone,
          });

          console.info(
            `[EQUIPMENT OK] '${cardId}' acoplado a '${parentObject.name || targetBone}'.`
          );
          this.triggerAttachGlow(parentObject);
          resolve(accessoryMesh);
        },
        undefined,
        (error) => {
          if (this.pendingLoads.get(cardId) === loadToken) {
            this.pendingLoads.delete(cardId);
          }
          console.error(
            `[EQUIPMENT ERROR] Error cargando asset: ${modelUrl}`,
            error
          );
          reject(error);
        }
      );
    });
  }

  /**
   * Retira un equipamiento equipado o cancela su carga pendiente.
   * @param {string} cardId
   * @returns {boolean}
   */
  detachEquipment(cardId) {
    let changed = false;

    if (this.pendingLoads.has(cardId)) {
      this.pendingLoads.delete(cardId);
      changed = true;
    }

    const item = this.equippedItems.get(cardId);
    if (!item) {
      return changed;
    }

    item.parent.remove(item.mesh);
    this.#disposeObject(item.mesh);
    this.equippedItems.delete(cardId);

    console.info(`[EQUIPMENT] '${cardId}' removido.`);
    return true;
  }

  /**
   * Retira todo el equipamiento actual.
   */
  clearAll() {
    for (const cardId of [
      ...this.pendingLoads.keys(),
      ...this.equippedItems.keys(),
    ]) {
      this.detachEquipment(cardId);
    }
  }

  /**
   * Busca primero coincidencia exacta y luego parcial.
   *
   * @param {string} searchTerm
   * @returns {THREE.Bone|null}
   */
  findBone(searchTerm) {
    if (!searchTerm || !this.characterModel) {
      return null;
    }

    const term = String(searchTerm).trim().toLowerCase();
    if (!term) {
      return null;
    }

    const exact = this.bonesMap.get(term);
    if (exact) {
      return exact;
    }

    for (const [name, bone] of this.bonesMap.entries()) {
      if (name.includes(term)) {
        return bone;
      }
    }

    console.warn(
      `[EQUIPMENT] No se encontró '${searchTerm}'. Se usará la raíz del personaje.`
    );
    return null;
  }

  /**
   * Pulso visual al instalar un accesorio.
   * @param {THREE.Object3D} parentObject
   */
  triggerAttachGlow(parentObject) {
    const THREE_NS = globalThis.THREE;
    if (!THREE_NS || !parentObject) {
      return;
    }

    const flashLight = new THREE_NS.PointLight(0x00e1ff, 5, 2);
    parentObject.add(flashLight);

    const startedAt = performance.now();
    const duration = 260;

    const animateGlow = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      flashLight.intensity = 5 * (1 - progress);

      if (progress >= 1) {
        parentObject.remove(flashLight);
        return;
      }

      requestAnimationFrame(animateGlow);
    };

    requestAnimationFrame(animateGlow);
  }

  #validateConfig(config) {
    if (!config || typeof config !== "object") {
      throw new TypeError("La configuración del equipamiento debe ser un objeto.");
    }
    if (!config.cardId || typeof config.cardId !== "string") {
      throw new TypeError("config.cardId es obligatorio.");
    }
    if (!config.modelUrl || typeof config.modelUrl !== "string") {
      throw new TypeError("config.modelUrl es obligatorio.");
    }
    if (!config.targetBone || typeof config.targetBone !== "string") {
      throw new TypeError("config.targetBone es obligatorio.");
    }

    for (const [name, value] of [
      ["offsetPos", config.offsetPos],
      ["offsetRot", config.offsetRot],
      ["scale", config.scale],
    ]) {
      if (value !== undefined && (!Array.isArray(value) || value.length !== 3)) {
        throw new TypeError(`config.${name} debe ser un array [x, y, z].`);
      }
    }
  }

  #disposeObject(object) {
    object.traverse((child) => {
      if (!child || !child.isMesh) {
        return;
      }

      if (child.geometry && typeof child.geometry.dispose === "function") {
        child.geometry.dispose();
      }

      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material];

      for (const material of materials) {
        if (material && typeof material.dispose === "function") {
          material.dispose();
        }
      }
    });
  }
}
