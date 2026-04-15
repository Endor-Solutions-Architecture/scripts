using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"SgoI4fAixhxv","alg":"RS256","n":"HfHVEm7DQehCUh5YtHD9OD-XOjY9rIGlurM5vuqiXutn_b0n","e":"AQAB","d":"9saH1iykYbhL8KuNyVucyA62sKYM7bj7cmh9fGXGdtMej_5kLlAgIF4NHh-Tpb7j"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"SgoI4fAixhxv\",\"alg\":\"RS256\",\"n\":\"HfHVEm7DQehCUh5YtHD9OD-XOjY9rIGlurM5vuqiXutn_b0n\",\"e\":\"AQAB\",\"d\":\"9saH1iykYbhL8KuNyVucyA62sKYM7bj7cmh9fGXGdtMej_5kLlAgIF4NHh-Tpb7j\"}";
    var key = new JsonWebKey(jwk);
  }
}
