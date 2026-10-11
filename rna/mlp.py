"""Red Neuronal Artificial Multicapa (MLP) implementada en Python puro.

El protocolo plantea un Perceptrón Multicapa cuya salida es el Índice de
Rentabilidad Regenerativa. Se implementa sin dependencias externas para que el
proyecto corra en cualquier equipo sin compilar paquetes científicos; la
arquitectura, el algoritmo (retropropagación con descenso de gradiente) y las
métricas son las mismas que entregaría TensorFlow/Keras u Orange Data Mining
para un problema de esta escala.

Arquitectura: n entradas → capa oculta (tanh) → 1 salida (sigmoide).
"""

import math
import random


class MLP:
    def __init__(self, n_entradas, n_ocultas=8, semilla=42):
        self.n_entradas = n_entradas
        self.n_ocultas = n_ocultas
        rng = random.Random(semilla)
        # Inicialización de Xavier: mantiene la varianza de la señal entre capas.
        limite_1 = math.sqrt(6.0 / (n_entradas + n_ocultas))
        limite_2 = math.sqrt(6.0 / (n_ocultas + 1))
        self.w1 = [[rng.uniform(-limite_1, limite_1) for _ in range(n_ocultas)]
                   for _ in range(n_entradas)]
        self.b1 = [0.0] * n_ocultas
        self.w2 = [rng.uniform(-limite_2, limite_2) for _ in range(n_ocultas)]
        self.b2 = 0.0
        self.min_x = [0.0] * n_entradas
        self.max_x = [1.0] * n_entradas

    # ---------- normalización ----------

    def ajustar_escala(self, X):
        n = len(X[0])
        self.min_x = [min(fila[j] for fila in X) for j in range(n)]
        self.max_x = [max(fila[j] for fila in X) for j in range(n)]

    def _escalar(self, x):
        return [
            (x[j] - self.min_x[j]) / ((self.max_x[j] - self.min_x[j]) or 1.0)
            for j in range(self.n_entradas)
        ]

    # ---------- propagación ----------

    def _adelante(self, x_esc):
        h = []
        for k in range(self.n_ocultas):
            z = self.b1[k] + sum(x_esc[j] * self.w1[j][k] for j in range(self.n_entradas))
            h.append(math.tanh(z))
        z2 = self.b2 + sum(h[k] * self.w2[k] for k in range(self.n_ocultas))
        y = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, z2))))
        return h, y

    def predecir(self, x):
        _, y = self._adelante(self._escalar(x))
        return y

    # ---------- entrenamiento ----------

    def entrenar(self, X, y, epocas=300, lr=0.05, semilla=42, validacion=0.2):
        """Retropropagación con descenso de gradiente estocástico."""
        rng = random.Random(semilla)
        self.ajustar_escala(X)
        datos = [(self._escalar(X[i]), y[i]) for i in range(len(X))]
        rng.shuffle(datos)

        corte = int(len(datos) * (1 - validacion))
        entrenamiento, prueba = datos[:corte], datos[corte:]
        historial = []

        for epoca in range(epocas):
            rng.shuffle(entrenamiento)
            for x_esc, objetivo in entrenamiento:
                h, salida = self._adelante(x_esc)
                # dL/dz2 para MSE con activación sigmoide en la salida
                d_z2 = (salida - objetivo) * salida * (1 - salida)
                grad_w2 = [d_z2 * h[k] for k in range(self.n_ocultas)]
                d_h = [d_z2 * self.w2[k] * (1 - h[k] ** 2) for k in range(self.n_ocultas)]

                for k in range(self.n_ocultas):
                    self.w2[k] -= lr * grad_w2[k]
                self.b2 -= lr * d_z2
                for j in range(self.n_entradas):
                    xj = x_esc[j]
                    if xj == 0.0:
                        continue
                    for k in range(self.n_ocultas):
                        self.w1[j][k] -= lr * d_h[k] * xj
                for k in range(self.n_ocultas):
                    self.b1[k] -= lr * d_h[k]

            if epoca % max(1, epocas // 20) == 0 or epoca == epocas - 1:
                historial.append({"epoca": epoca + 1, "mse": round(self._mse(entrenamiento), 6)})

        return {"historial": historial, "metricas": self.metricas(prueba or entrenamiento)}

    def _mse(self, datos):
        if not datos:
            return 0.0
        return sum((self._adelante(x)[1] - t) ** 2 for x, t in datos) / len(datos)

    def metricas(self, datos):
        """MSE, RMSE, MAE y R² sobre el conjunto de validación."""
        if not datos:
            return {}
        pred = [self._adelante(x)[1] for x, _ in datos]
        real = [t for _, t in datos]
        n = len(real)
        mse = sum((pred[i] - real[i]) ** 2 for i in range(n)) / n
        mae = sum(abs(pred[i] - real[i]) for i in range(n)) / n
        media = sum(real) / n
        ss_tot = sum((r - media) ** 2 for r in real)
        r2 = 1 - (mse * n) / ss_tot if ss_tot else 0.0
        return {
            "n_validacion": n,
            "mse": round(mse, 6),
            "rmse": round(math.sqrt(mse), 6),
            "mae": round(mae, 6),
            "r2": round(r2, 4),
        }

    # ---------- persistencia ----------

    def a_dict(self):
        return {
            "n_entradas": self.n_entradas,
            "n_ocultas": self.n_ocultas,
            "w1": self.w1,
            "b1": self.b1,
            "w2": self.w2,
            "b2": self.b2,
            "min_x": self.min_x,
            "max_x": self.max_x,
        }

    @classmethod
    def desde_dict(cls, data):
        red = cls(data["n_entradas"], data["n_ocultas"])
        red.w1 = data["w1"]
        red.b1 = data["b1"]
        red.w2 = data["w2"]
        red.b2 = data["b2"]
        red.min_x = data["min_x"]
        red.max_x = data["max_x"]
        return red
