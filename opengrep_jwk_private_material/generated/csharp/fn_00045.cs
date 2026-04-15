using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"8xOvVP8o6Ss2","alg":"RS256","n":"eBKxC71bqL4qb5SPmxoW-bYaSabi0u6mIAhUWED7FwkkiMod","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"8xOvVP8o6Ss2\",\"alg\":\"RS256\",\"n\":\"eBKxC71bqL4qb5SPmxoW-bYaSabi0u6mIAhUWED7FwkkiMod\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
