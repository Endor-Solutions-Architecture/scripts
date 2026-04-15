using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"oct","kid":"9_YzLd1meRtw","alg":"HS256","k":"MJGg4EevDuTHqdfeEu4QbtDUfeywqzsNVUffTyf8EZ9vUAwteaC-6kzqp-SWOB1V"}
    var jwk = "{\"kty\":\"oct\",\"kid\":\"9_YzLd1meRtw\",\"alg\":\"HS256\",\"k\":\"MJGg4EevDuTHqdfeEu4QbtDUfeywqzsNVUffTyf8EZ9vUAwteaC-6kzqp-SWOB1V\"}";
    var key = new JsonWebKey(jwk);
  }
}
